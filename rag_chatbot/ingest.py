# ingest.py
"""
Módulo de Ingestão de Dados (PDFs).

Atualizado para:
1. Usar settings.py.
2. Corrigir problema de 'file handle' no Windows (time.sleep).
"""

import os
import shutil
import re
import time
from tqdm import tqdm
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Importar a nova configuração
from settings import settings


# --- FUNÇÃO PARA RETIRAR O RODAPÉ ---
def clean_page_content(page_text):
    footer_pattern_sei = r"(Edital|Minuta)\s+\d+\s+SEI \d+\s*/\s*pg\.\s*\d+"
    page_text = re.sub(footer_pattern_sei, "", page_text, flags=re.IGNORECASE)
    page_text = re.sub(r"\n\s*\n", "\n", page_text)
    return page_text.strip()


def process_documents():
    """Carrega, divide e vetoriza os documentos PDF."""
    print("Iniciando a ingestão de documentos...")

    # Garante que pastas existam
    if not os.path.exists(settings.DOCS_DIR):
        print(f"Diretório de docs não encontrado: {settings.DOCS_DIR}")
        return

    pdf_files = [f for f in os.listdir(settings.DOCS_DIR) if f.endswith(".pdf")]

    if not pdf_files:
        print(f"Nenhum documento PDF encontrado no diretório: {settings.DOCS_DIR}")
        return

    print(
        f"Encontrados {len(pdf_files)} arquivos PDF. Iniciando carregamento e limpeza..."
    )

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    # --- LÓGICA DE CARREGAMENTO ---
    all_docs = []

    for filename in tqdm(pdf_files, desc="Processando PDFs", unit="arquivo"):
        filepath = os.path.join(settings.DOCS_DIR, filename)
        loader = PyMuPDFLoader(filepath)

        try:
            docs_por_pagina = loader.load()

            for doc in docs_por_pagina:
                doc.page_content = clean_page_content(doc.page_content)

                # Sanitização de caminho (Path -> str -> relpath)
                if "source" in doc.metadata:
                    try:
                        doc.metadata["source"] = os.path.relpath(
                            doc.metadata["source"], settings.BASE_DIR
                        )
                    except ValueError:
                        pass

            all_docs.extend(docs_por_pagina)

        except Exception as e:
            print(f"\nErro ao carregar ou limpar o arquivo {filename}: {e}")

    if not all_docs:
        print("Nenhum documento pôde ser processado com sucesso.")
        return

    print("Documentos limpos. Iniciando divisão em chunks...")
    all_chunks = text_splitter.split_documents(all_docs)

    print(f"Documentos divididos em {len(all_chunks)} chunks.")

    # 3. Inicializar modelo de embedding
    embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL_NAME)

    # 3.5. Limpar o banco de dados vetorial antigo
    vector_db_path = str(settings.VECTOR_DB_DIR)
    print(f"Verificando e limpando diretório antigo: {vector_db_path}")

    if os.path.isdir(vector_db_path):
        try:
            shutil.rmtree(vector_db_path)
            time.sleep(1)  # Fix para Windows
            print(f"Diretório antigo removido com sucesso.")
        except OSError as e:
            print(f"Erro ao remover o diretório: {e}")
            print("Feche terminais/apps usando o banco e tente novamente.")
            return
    elif os.path.exists(vector_db_path):
        os.remove(vector_db_path)

    # 4. Criar e persistir o banco de dados vetorial
    print("Iniciando vetorização e criação do DB...")

    vectordb = Chroma.from_documents(
        documents=all_chunks,
        embedding=embeddings,
        persist_directory=vector_db_path,
    )

    print(f"Banco de vetores criado em '{vector_db_path}'.")
    print("Ingestão concluída.")


if __name__ == "__main__":
    process_documents()
