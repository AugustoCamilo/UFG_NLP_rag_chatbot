# vector_retriever.py
import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder
from langchain_core.documents import Document
from typing import List, Tuple

# Importar o arquivo de configuração
import config


class VectorRetriever:
    """
    Carrega o banco de vetores Chroma e o modelo Re-Ranker para
    executar a busca em duas etapas (Recall + Re-Ranking).
    """

    def __init__(self):
        print("Inicializando o VectorRetriever...")

        if not os.path.exists(config.VECTOR_DB_DIR):  #
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
            )  #

            # 2. Carregar o banco de vetores Chroma
            print(f"Carregando banco de vetores de '{config.VECTOR_DB_DIR}'...")
            self.vectordb = Chroma(
                persist_directory=config.VECTOR_DB_DIR,
                embedding_function=self.embeddings,
            )  #

            # 3. Carregar o modelo de Re-Ranker (CrossEncoder)
            print("Carregando modelo de Re-Ranking (Cross-Encoder)...")
            self.reranker = CrossEncoder(config.RERANKER_MODEL_NAME)  #
            print("VectorRetriever inicializado com sucesso.")

        except Exception as e:
            print(f"Ocorreu um erro ao inicializar o VectorRetriever: {e}")  #
            raise

    def retrieve_context(self, query: str) -> List[Document]:
        """
        Executa a busca e o re-ranking e retorna apenas a lista de Documentos.
        Mantido para compatibilidade com o rag_chain.py.
        """
        results_with_scores = self.retrieve_context_with_scores(query)  #
        # Extrai apenas os documentos da tupla
        return [doc for doc, score in results_with_scores]  #

    def retrieve_context_with_scores(self, query: str) -> List[Tuple[Document, float]]:
        """
        Executa a busca vetorial (Recall) seguida pelo Re-Ranking (Precision)
        e retorna os Documentos junto com seus scores de relevância.
        """
        print(f"Iniciando Etapa 1 (Recall) para: '{query}'")
        # ETAPA 1: RECALL (Busca Vetorial Rápida)
        results_with_scores = self.vectordb.similarity_search_with_score(
            query, k=config.SEARCH_K_RAW
        )  #

        if not results_with_scores:  #
            print("Nenhum resultado encontrado na busca vetorial.")
            return []

        print(f"Etapa 1 concluída. {len(results_with_scores)} chunks recuperados.")
        print("Iniciando Etapa 2 (Re-Ranking)...")

        # ETAPA 2: RE-RANKING (Reclassificação Inteligente)
        try:
            # 1. Criar pares de [pergunta, chunk]
            pairs = [[query, doc.page_content] for doc, score in results_with_scores]  #

            # 2. Obter os novos scores do Re-Ranker
            rerank_scores = self.reranker.predict(pairs)  #

            # 3. Combinar os documentos com seus novos scores
            reranked_results = list(zip(results_with_scores, rerank_scores))  #

            # 4. Ordenar pelos novos scores (MAIOR é MELHOR)
            reranked_results.sort(key=lambda x: x[1], reverse=True)  #

            # 5. Pegar o Top-K final
            top_k_results = reranked_results[: config.SEARCH_K_FINAL]  #

            # 6. Formatar a saída para (Documento, score_relevancia)
            final_results = [
                (doc, rerank_score) for (doc, old_score), rerank_score in top_k_results
            ]  #

            print(f"Etapa 2 concluída. {len(final_results)} chunks selecionados.")
            return final_results

        except Exception as e:
            print(f"Erro durante o Re-Ranking: {e}")  #
            return []

    # --- INÍCIO DA NOVA FUNÇÃO ---
    def retrieve_context_vector_search_only(
        self, query: str
    ) -> List[Tuple[Document, float]]:
        """
        Executa APENAS a busca vetorial (Recall) e retorna os resultados
        brutos ordenados por distância.
        """
        print(
            f"Iniciando Etapa 1 (Recall APENAS, k={config.SEARCH_K_FINAL}) para: '{query}'"
        )
        try:
            # Busca diretamente os K_FINAL (ex: 3) chunks mais próximos
            results_with_scores = self.vectordb.similarity_search_with_score(
                query, k=config.SEARCH_K_FINAL
            )

            if not results_with_scores:
                print("Nenhum resultado encontrado na busca vetorial.")
                return []

            # Ordena por score (distância - MENOR é MELHOR para Chroma)
            # Embora o Chroma já retorne ordenado, esta é uma garantia.
            results_with_scores.sort(key=lambda x: x[1])  #

            print(
                f"Etapa 1 (Recall) concluída. {len(results_with_scores)} chunks recuperados."
            )

            # Retorna a lista (que já tem tamanho K_FINAL), sem fatiar
            return results_with_scores

        except Exception as e:
            print(f"Erro durante a busca vetorial: {e}")
            return []

    # --- FIM DA NOVA FUNÇÃO ---

    def get_all_chunks(self) -> dict:
        """
        Expõe o método .get() do banco de dados Chroma.
        Usado pelo read_db_vector.py para listar e exportar chunks.
        """
        if self.vectordb:
            return self.vectordb.get()  #
        return {"documents": [], "metadatas": []}
