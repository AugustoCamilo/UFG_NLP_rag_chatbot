# vector_retriever.py
"""
Módulo Central de Recuperação de Informação (Retriever).

Atualizado para:
1. Usar settings.py em vez de config.py.
"""

import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder
from langchain_core.documents import Document
from typing import List, Tuple

# Importar a nova configuração
from settings import settings


class VectorRetriever:
    """
    Carrega o banco de vetores Chroma e o modelo Re-Ranker para
    executar a busca em duas etapas (Recall + Re-Ranking).
    """

    def __init__(self):
        print("Inicializando o VectorRetriever...")

        # Verifica existência do diretório (convertendo Path para str se necessário)
        db_dir_str = str(settings.VECTOR_DB_DIR)

        if not os.path.exists(db_dir_str):
            print(
                f"Erro: Diretório do banco de vetores não encontrado em '{db_dir_str}'"
            )
            print(
                "Por favor, execute o script 'ingest.py' ou 'ingest_xml.py' primeiro."
            )
            raise FileNotFoundError(db_dir_str)

        try:
            # 1. Carregar modelo de embedding (para ler o Chroma DB)
            print("Carregando modelo de embedding...")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL_NAME
            )

            # 2. Carregar o banco de vetores Chroma
            print(f"Carregando banco de vetores de '{db_dir_str}'...")
            self.vectordb = Chroma(
                persist_directory=db_dir_str,
                embedding_function=self.embeddings,
            )

            # 3. Carregar o modelo de Re-Ranker (Cross-Encoder)
            print("Carregando modelo de Re-Ranking (Cross-Encoder)...")
            # self.reranker = CrossEncoder(settings.RERANKER_MODEL_NAME)
            self.cross_encoder = CrossEncoder(
                settings.RERANK_MODEL,
                max_length=512,
                device=self.device,
                automodel_args={"low_cpu_mem_usage": False},
            )
            print("VectorRetriever inicializado com sucesso.")

        except Exception as e:
            print(f"Ocorreu um erro ao inicializar o VectorRetriever: {e}")
            raise

    def retrieve_context(self, query: str) -> List[Document]:
        """
        Executa a busca e o re-ranking e retorna apenas a lista de Documentos.
        """
        results_with_scores = self.retrieve_context_with_scores(query)
        return [doc for doc, score in results_with_scores]

    def retrieve_context_with_scores(self, query: str) -> List[Tuple[Document, float]]:
        """
        Executa a busca vetorial (Recall) seguida pelo Re-Ranking (Precision).
        """
        print(f"Iniciando Etapa 1 (Recall) para: '{query}'")

        # ETAPA 1: RECALL (Busca Vetorial Rápida)
        results_with_scores = self.vectordb.similarity_search_with_score(
            query, k=settings.SEARCH_K_RAW
        )

        if not results_with_scores:
            print("Nenhum resultado encontrado na busca vetorial.")
            return []

        print(f"Etapa 1 concluída. {len(results_with_scores)} chunks recuperados.")
        print("Iniciando Etapa 2 (Re-Ranking)...")

        # ETAPA 2: RE-RANKING
        try:
            pairs = [[query, doc.page_content] for doc, score in results_with_scores]
            rerank_scores = self.reranker.predict(pairs)

            reranked_results = list(zip(results_with_scores, rerank_scores))
            reranked_results.sort(key=lambda x: x[1], reverse=True)

            top_k_results = reranked_results[: settings.SEARCH_K_FINAL]

            final_results = [
                (doc, float(rerank_score))
                for (doc, old_score), rerank_score in top_k_results
            ]

            print(f"Etapa 2 concluída. {len(final_results)} chunks selecionados.")
            return final_results

        except Exception as e:
            print(f"Erro durante o Re-Ranking: {e}")
            return []

    def retrieve_context_vector_search_only(
        self, query: str
    ) -> List[Tuple[Document, float]]:
        """
        Executa APENAS a busca vetorial (Recall).
        """
        print(
            f"Iniciando Etapa 1 (Recall APENAS, k={settings.SEARCH_K_FINAL}) para: '{query}'"
        )
        try:
            results_with_scores = self.vectordb.similarity_search_with_score(
                query, k=settings.SEARCH_K_FINAL
            )

            if not results_with_scores:
                print("Nenhum resultado encontrado na busca vetorial.")
                return []

            # Ordena por score (distância - MENOR é MELHOR para Chroma padrão, mas varia pela métrica)
            results_with_scores.sort(key=lambda x: x[1])

            print(
                f"Etapa 1 (Recall) concluída. {len(results_with_scores)} chunks recuperados."
            )
            return results_with_scores

        except Exception as e:
            print(f"Erro durante a busca vetorial: {e}")
            return []

    def get_all_chunks(self) -> dict:
        """
        Expõe o método .get() do banco de dados Chroma.
        """
        if self.vectordb:
            return self.vectordb.get()
        return {"documents": [], "metadatas": []}
