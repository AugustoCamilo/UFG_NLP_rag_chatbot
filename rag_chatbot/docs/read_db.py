# read_db.py
import os
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
import sys # Importado para o caso de erro

# --- Configurações ---
# Garanta que estas configurações são IDÊNTICAS às do seu ingest.py
VECTOR_DB_DIR = '../vector_db'
EMBEDDING_MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'

def load_database():
    """Carrega o banco de vetores existente."""
    if not os.path.exists(VECTOR_DB_DIR):
        print(f"Erro: Diretório do banco de vetores não encontrado em '{VECTOR_DB_DIR}'")
        print("Certifique-se de que o caminho está correto e execute o ingest.py primeiro.")
        return None
    
    try:
        print("Inicializando modelo de embedding (pode levar um momento)...")
        # É crucial usar o *mesmo* modelo de embedding que foi usado para criar o banco
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        
        print(f"Carregando banco de vetores de '{VECTOR_DB_DIR}'...")
        vectordb = Chroma(
            persist_directory=VECTOR_DB_DIR,
            embedding_function=embeddings
        )
        print("Banco de vetores carregado com sucesso.")
        return vectordb
        
    except Exception as e:
        print(f"Ocorreu um erro ao carregar o banco de dados: {e}")
        return None

def read_all_chunks(vectordb):
    """
    Função para verificar. Lê e exibe (parcialmente) todos os chunks 
    armazenados no banco de dados.
    """
    print("\n--- [MODO 1: Lendo Todos os Chunks Armazenados] ---")
    
    data = vectordb.get() 
    documents = data.get('documents')
    metadatas = data.get('metadatas')
    
    if not documents:
        print("O banco de dados está vazio. Nenhum chunk encontrado.")
        return

    print(f"Total de chunks encontrados no banco: {len(documents)}")
    
    for i in range(len(documents)):
        doc_text = documents[i]
        source = metadatas[i].get('source', 'N/A')
        
        print("\n" + "=" * 50)
        print(f"Chunk {i+1} (Fonte: {source})")
        print("=" * 50)
        print(f"{doc_text[:350]}...") 
        
    print("\n" + "=" * 50)
    print("Leitura de todos os chunks concluída.")

def search_chunks(vectordb, query):
    """
    Função principal. Executa uma busca por similaridade para 
    encontrar os chunks mais relevantes para uma pergunta.
    """
    print("\n--- [MODO 2: Testando Busca por Similaridade] ---")
    
    if not query:
        print("Nenhuma query (pergunta) fornecida para a busca.")
        return
            
    print(f"Buscando por: '{query}'")
    
    # k=3 significa que queremos os 3 resultados mais relevantes
    try:
        results = vectordb.similarity_search(query, k=3)
        
        if not results:
            print("Nenhum resultado relevante encontrado para esta busca.")
            return
        
        print(f"\nEncontrados {len(results)} resultados relevantes:")
        
        for i, doc in enumerate(results):
            source = doc.metadata.get('source', 'N/A')
            print("\n" + "-" * 50)
            print(f"Resultado Relevante {i+1} (Fonte: {source})")
            print("-" * 50)
            print(doc.page_content) 
            
    except Exception as e:
        print(f"Ocorreu um erro durante a busca: {e}")

# --- BLOCO PRINCIPAL (ALTERADO) ---
if __name__ == '__main__':
    vectordb = load_database()
    
    if vectordb:
        print("\n--- [Modo de Validação de Chunks] ---")
        print("O banco de dados foi carregado com sucesso.")
        print("\nInstruções:")
        print("  1. Digite sua consulta (pergunta) para testar a busca.")
        print("  2. Digite '!todos' para listar todos os chunks no banco.")
        print("  3. Digite 'sair' para encerrar o script.")
        
        # Loop interativo
        while True:
            # Pede a entrada do usuário
            query = input("\nSua consulta (ou 'sair' / '!todos'): ")
            
            # 1. Verifica se quer sair
            if query.lower() == 'sair':
                print("Encerrando o script...")
                break
            
            # 2. Verifica se quer listar todos
            elif query == '!todos':
                read_all_chunks(vectordb)
            
            # 3. Executa a busca normal
            elif query.strip() == "":
                print("Por favor, digite uma consulta válida.")
            
            else:
                # O search_chunks já imprime os resultados
                search_chunks(vectordb, query=query)
    
    else:
        print("\nNão foi possível carregar o banco de dados. Encerrando.")
        sys.exit(1) # Termina o script se o BD não for carregado