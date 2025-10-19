# ingest.py
import os
# Importação da biblioteca tqdm
from tqdm import tqdm 
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


# Caminhos
DOCS_DIR = '.'
VECTOR_DB_DIR = '../vector_db'
EMBEDDING_MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'

def process_documents():
    """Carrega, divide e vetoriza os documentos PDF."""
    print("Iniciando a ingestão de documentos...")
    
    # --- Alteração Inicia Aqui ---

    # 1. Carregar documentos
    
    # Primeiro, lista todos os arquivos PDF
    pdf_files = [f for f in os.listdir(DOCS_DIR) if f.endswith('.pdf')]
    
    if not pdf_files:
        print(f"Nenhum documento PDF encontrado no diretório: {DOCS_DIR}")
        return

    print(f"Encontrados {len(pdf_files)} arquivos PDF. Iniciando carregamento...")

    documents = []
    # Use tqdm() para envolver a lista de arquivos e criar a barra de progresso
    for filename in tqdm(pdf_files, desc="Carregando PDFs", unit="arquivo"):
        filepath = os.path.join(DOCS_DIR, filename)
        loader = PyPDFLoader(filepath)
        try:
            documents.extend(loader.load())
        except Exception as e:
            # \n é importante para pular a linha da barra de progresso
            print(f"\nErro ao carregar o arquivo {filename}: {e}") 
            # Continua para o próximo arquivo

    # --- Alteração Termina Aqui ---

    if not documents:
        print("Nenhum documento pôde ser carregado com sucesso.")
        return

    # 2. Dividir documentos em chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(documents)
    print(f"Documentos divididos em {len(chunks)} chunks.")

    # 3. Inicializar modelo de embedding
    # Usará a CPU por padrão.
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

    # 4. Criar e persistir o banco de dados vetorial
    # Usando ChromaDB com persistência local
    print("Iniciando vetorização e criação do banco de dados (pode levar um tempo)...")
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=VECTOR_DB_DIR
    )
    
    vectordb.persist()
    print(f"Banco de vetores criado e salvo em '{VECTOR_DB_DIR}'.")
    print("Ingestão concluída.")

if __name__ == '__main__':
    # Coloque seus arquivos PDF na pasta 'docs' antes de rodar este script.
    process_documents()