# ingest.py
import os
import shutil
from tqdm import tqdm
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Importar o arquivo de configuração
import config


def process_documents():
    """Carrega, divide e vetoriza os documentos PDF."""
    print("Iniciando a ingestão de documentos...")

    # 1. Carregar documentos
    pdf_files = [f for f in os.listdir(config.DOCS_DIR) if f.endswith(".pdf")]

    if not pdf_files:
        print(f"Nenhum documento PDF encontrado no diretório: {config.DOCS_DIR}")
        return

    print(
        f"Encontrados {len(pdf_files)} arquivos PDF. Iniciando carregamento e divisão..."
    )

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    all_chunks = []

    for filename in tqdm(pdf_files, desc="Processando PDFs", unit="arquivo"):
        filepath = os.path.join(config.DOCS_DIR, filename)
        loader = PyMuPDFLoader(filepath)

        try:
            chunks = loader.load_and_split(text_splitter=text_splitter)
            all_chunks.extend(chunks)

        except Exception as e:
            print(f"\nErro ao carregar ou dividir o arquivo {filename}: {e}")

    if not all_chunks:
        print("Nenhum documento pôde ser processado com sucesso.")
        return

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
