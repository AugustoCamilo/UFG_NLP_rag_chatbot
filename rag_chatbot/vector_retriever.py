# vector_retriever.py
import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder
from langchain_core.documents import Document
from typing import List

# Importar o arquivo de configuração
import config


class VectorRetriever:
    """
    Carrega o banco de vetores Chroma e o modelo Re-Ranker para
    executar a busca em duas etapas (Recall + Re-Ranking).
    """

    def __init__(self):
        print("Inicializando o VectorRetriever...")

        if not os.path.exists(config.VECTOR_DB_DIR):
            print(
                f"Erro: Diretório do banco de vetores não encontrado em '{config.VECTOR_DB_DIR}'"
            )
            print("Por favor, execute o script 'ingest.py' primeiro.")
            raise FileNotFoundError(config.VECTOR_DB_DIR)

        try:
            # 1. Carregar modelo de embedding (para ler o Chroma DB)
            print("Carregando modelo de embedding...")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=config.EMBEDDING_MODEL_NAME
            )

            # 2. Carregar o banco de vetores Chroma
            print(f"Carregando banco de vetores de '{config.VECTOR_DB_DIR}'...")
            self.vectordb = Chroma(
                persist_directory=config.VECTOR_DB_DIR,
                embedding_function=self.embeddings,
            )

            # 3. Carregar o modelo de Re-Ranker (CrossEncoder)
            print("Carregando modelo de Re-Ranking (Cross-Encoder)...")
            self.reranker = CrossEncoder(config.RERANKER_MODEL_NAME)
            print("VectorRetriever inicializado com sucesso.")

        except Exception as e:
            print(f"Ocorreu um erro ao inicializar o VectorRetriever: {e}")
            raise

    def retrieve_context(self, query: str) -> List[Document]:
        """
        Executa a busca vetorial (Recall) seguida pelo Re-Ranking (Precision).
        """
        print(f"Iniciando Etapa 1 (Recall) para: '{query}'")
        # ETAPA 1: RECALL (Busca Vetorial Rápida)
        # Busca K "brutos" resultados
        results_with_scores = self.vectordb.similarity_search_with_score(
            query, k=config.SEARCH_K_RAW
        )

        if not results_with_scores:
            print("Nenhum resultado encontrado na busca vetorial.")
            return []

        print(f"Etapa 1 concluída. {len(results_with_scores)} chunks recuperados.")
        print("Iniciando Etapa 2 (Re-Ranking)...")

        # ETAPA 2: RE-RANKING (Reclassificação Inteligente)
        try:
            # 1. Criar pares de [pergunta, chunk]
            pairs = [[query, doc.page_content] for doc, score in results_with_scores]

            # 2. Obter os novos scores do Re-Ranker
            rerank_scores = self.reranker.predict(pairs)

            # 3. Combinar os documentos com seus novos scores
            reranked_results = list(zip(results_with_scores, rerank_scores))

            # 4. Ordenar pelos novos scores (MAIOR é MELHOR)
            reranked_results.sort(key=lambda x: x[1], reverse=True)

            # 5. Pegar o Top-K final
            top_k_results = reranked_results[: config.SEARCH_K_FINAL]

            # 6. Extrair apenas os Documentos
            final_docs = [doc for (doc, old_score), rerank_score in top_k_results]

            print(f"Etapa 2 concluída. {len(final_docs)} chunks selecionados.")
            return final_docs

        except Exception as e:
            print(f"Erro durante o Re-Ranking: {e}")
            return []
