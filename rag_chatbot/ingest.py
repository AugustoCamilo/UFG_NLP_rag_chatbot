# ingest.py
import os
import shutil
import re
from tqdm import tqdm
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Importar o arquivo de configuração
import config


# --- FUNÇÃO PARA RETIRAR O RODAPÉ ---
def clean_page_content(page_text):
    """
    Limpa o texto de uma página, removendo rodapés conhecidos usando Regex.

    !!! IMPORTANTE: Você DEVE personalizar esta função com os padrões
    do SEU rodapé específico.
    """

    # --- INÍCIO DA ÁREA DE PERSONALIZAÇÃO ---

    # Expressão regular para remover o rodapé do Edital/SEI
    # \d+ = um ou mais dígitos
    # \s+ = um ou mais espaços/tabs
    # \. = o caractere de ponto literal
    footer_pattern_sei = r"(Edital|Minuta)\s+\d+\s+SEI \d+\s*/\s*pg\.\s*\d+"

    # Aplica a remoção, ignorando maiúsculas/minúsculas
    page_text = re.sub(footer_pattern_sei, "", page_text, flags=re.IGNORECASE)

    # O exemplo 2 original foi removido, mas você pode mantê-lo
    # se também quiser remover rodapés genéricos "Página X"
    # footer_pattern_2 = r"\bPágina \d+( de \d+)?\b"
    # page_text = re.sub(footer_pattern_2, "", page_text, flags=re.IGNORECASE)

    # --- FIM DA ÁREA DE PERSONALIZAÇÃO ---

    # Remove linhas em branco excessivas que podem ter sido deixadas
    # após a remoção dos rodapés
    page_text = re.sub(r"\n\s*\n", "\n", page_text)

    return page_text.strip()


# --- FIM DA FUNÇÃO ---


def process_documents():
    """Carrega, divide e vetoriza os documentos PDF."""
    print("Iniciando a ingestão de documentos...")

    # 1. Carregar documentos
    pdf_files = [f for f in os.listdir(config.DOCS_DIR) if f.endswith(".pdf")]

    if not pdf_files:
        print(f"Nenhum documento PDF encontrado no diretório: {config.DOCS_DIR}")
        return

    print(
        f"Encontrados {len(pdf_files)} arquivos PDF. Iniciando carregamento e limpeza..."
    )

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    # --- LÓGICA DE CARREGAMENTO ---

    # Lista para guardar todas as páginas (como 'Document') JÁ LIMPAS
    all_docs = []

    for filename in tqdm(pdf_files, desc="Processando PDFs", unit="arquivo"):
        filepath = os.path.join(config.DOCS_DIR, filename)
        loader = PyMuPDFLoader(filepath)

        try:
            # 1. Carrega o PDF (uma lista de Documentos, 1 por página)
            docs_por_pagina = loader.load()

            # 2. Limpa o rodapé de CADA página
            for doc in docs_por_pagina:
                doc.page_content = clean_page_content(doc.page_content)

            # 3. Adiciona as páginas limpas à lista principal
            all_docs.extend(docs_por_pagina)

        except Exception as e:
            print(f"\nErro ao carregar ou limpar o arquivo {filename}: {e}")

    if not all_docs:
        print("Nenhum documento pôde ser processado com sucesso.")
        return

    # 4. Divide os documentos JÁ LIMPOS em chunks
    print("Documentos limpos. Iniciando divisão em chunks...")
    all_chunks = text_splitter.split_documents(all_docs)

    # --- FIM DA LÓGICA DE CARREGAMENTO ---

    print(f"Documentos divididos em {len(all_chunks)} chunks.")

    # 3. Inicializar modelo de embedding
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_NAME)

    # 3.5. Limpar o banco de dados vetorial antigo ANTES de criar um novo
    print(
        f"Verificando e limpando o diretório do banco de dados antigo: {config.VECTOR_DB_DIR}"
    )
    if os.path.isdir(config.VECTOR_DB_DIR):
        try:
            shutil.rmtree(config.VECTOR_DB_DIR)
            print(f"Diretório antigo '{config.VECTOR_DB_DIR}' removido com sucesso.")
        except OSError as e:
            print(f"Erro ao remover o diretório {config.VECTOR_DB_DIR}: {e}")
            print(
                "Por favor, feche todos os programas que possam estar usando este diretório e tente novamente."
            )
            return
    elif os.path.exists(config.VECTOR_DB_DIR):
        print(
            f"Atenção: O caminho '{config.VECTOR_DB_DIR}' existe, mas não é um diretório. Removendo..."
        )
        try:
            os.remove(config.VECTOR_DB_DIR)
        except OSError as e:
            print(f"Erro ao remover o arquivo {config.VECTOR_DB_DIR}: {e}")
            return
    else:
        print("Nenhum banco de dados antigo encontrado. Criando um novo.")

    # 4. Criar e persistir o banco de dados vetorial
    print("Iniciando vetorização e criação do banco de dados (pode levar um tempo)...")

    # A classe Chroma agora é importada do langchain_chroma
    vectordb = Chroma.from_documents(
        documents=all_chunks,
        embedding=embeddings,
        persist_directory=config.VECTOR_DB_DIR,
    )

    print(f"Banco de vetores criado e salvo em '{config.VECTOR_DB_DIR}'.")
    print("Ingestão concluída.")


if __name__ == "__main__":
    process_documents()
