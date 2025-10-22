# read_db.py
import os

# --- ALTERAÇÃO: Importar Chroma do novo pacote ---
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
import sys


# Importar o arquivo de configuração
import config


def load_database():
    """Carrega o banco de vetores existente."""
    if not os.path.exists(config.VECTOR_DB_DIR):
        print(
            f"Erro: Diretório do banco de vetores não encontrado em '{config.VECTOR_DB_DIR}'"
        )
        print(
            "Certifique-se de que o caminho está correto e execute o ingest.py "
            "primeiro."
        )
        return None

    try:
        print("Inicializando modelo de embedding (pode levar um momento)...")
        embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_NAME)

        print(f"Carregando banco de vetores de '{config.VECTOR_DB_DIR}'...")

        # A classe Chroma agora é importada do langchain_chroma
        vectordb = Chroma(
            persist_directory=config.VECTOR_DB_DIR, embedding_function=embeddings
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
    documents = data.get("documents")
    metadatas = data.get("metadatas")

    if not documents:
        print("O banco de dados está vazio. Nenhum chunk encontrado.")
        return

    print(f"Total de chunks encontrados no banco: {len(documents)}")

    for i in range(len(documents)):
        doc_text = documents[i]
        source = metadatas[i].get("source", "N/A")

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
    print("\n--- [MODO 2: Testando Busca por Similaridade Avançada] ---")

    if not query:
        print("Nenhuma query (pergunta) fornecida para a busca.")
        return

    print(
        f"Buscando por: '{query}' (Recuperando {config.SEARCH_K_RAW} chunks para análise...)"
    )

    try:
        results_with_scores = vectordb.similarity_search_with_score(
            query, k=config.SEARCH_K_RAW
        )

        if not results_with_scores:
            print("Nenhum resultado relevante encontrado para esta busca.")
            return

        sorted_results = sorted(results_with_scores, key=lambda x: x[1])

        top_k_results = sorted_results[: config.SEARCH_K_FINAL]

        print(
            f"\nExibindo os {config.SEARCH_K_FINAL} resultados MAIS RELEVANTES"
            f" (de {config.SEARCH_K_RAW} analisados):"
        )

        for i, (doc, score) in enumerate(top_k_results):
            source = doc.metadata.get("source", "N/A")
            print("\n" + "-" * 50)
            print(
                f"Resultado Relevante {i+1} (Fonte: {source}) " f"(Score: {score:.4f})"
            )
            print("-" * 50)
            print(doc.page_content)

    except Exception as e:
        print(f"Ocorreu um erro durante a busca: {e}")


# --- BLOCO PRINCIPAL (sem alterações) ---
if __name__ == "__main__":
    vectordb = load_database()

    if vectordb:
        print("\n--- [Modo de Validação de Chunks] ---")
        print("O banco de dados foi carregado com sucesso.")
        print("\nInstruções:")
        print("  1. Digite sua consulta (pergunta) para testar a busca.")
        print("  2. Digite '!todos' para listar todos os chunks no banco.")
        print("  3. Digite 'sair' para encerrar o script.")

        while True:
            query = input("\nSua consulta (ou 'sair' / '!todos'): ")

            if query.lower() == "sair":
                print("Encerrando o script...")
                break

            elif query == "!todos":
                read_all_chunks(vectordb)

            elif query.strip() == "":
                print("Por favor, digite uma consulta válida.")

            else:
                search_chunks(vectordb, query=query)

    else:
        print("\nNão foi possível carregar o banco de dados. Encerrando.")
        sys.exit(1)
