# vector_retriever.py
"""
Módulo Central de Recuperação de Informação (Retriever).

Esta classe (`VectorRetriever`) é o componente principal do RAG,
responsável por carregar os modelos de busca e executar a
recuperação de contexto.

Ela é inicializada uma vez (`@st.cache_resource`) e
utilizada tanto pelo `rag_chain.py` (em produção) quanto
pelo `validate_vector_db.py` (para avaliação).

---
### Arquitetura de Recuperação (Duas Etapas)
---

O `VectorRetriever` implementa uma estratégia de busca sofisticada
em duas etapas (Recall e Re-Ranking) para garantir tanto
velocidade quanto precisão.


1.  **Etapa 1: Recall (Busca Vetorial Ampla)**
    * Utiliza o `ChromaDB` (via `similarity_search_with_score`)
        para fazer uma busca vetorial rápida.
    * O objetivo é "lembrar" (recall) um conjunto amplo de
        chunks candidatos (`SEARCH_K_RAW`, ex: 20) que
        sejam semanticamente próximos da pergunta.
    * Esta etapa é rápida, mas pode conter "ruído" (chunks
        próximos, mas não perfeitamente relevantes).

2.  **Etapa 2: Re-Ranking (Busca de Precisão)**
    * Utiliza um modelo `CrossEncoder` (`self.reranker`),
        que é mais lento, porém muito mais preciso.
    * O Cross-Encoder não compara a pergunta com os chunks
        individualmente; ele compara a *pergunta e o chunk juntos* (`[pergunta, chunk_conteudo]`) para dar um score
        de relevância muito mais acurado.
    * Ele re-classifica os 20 chunks candidatos e seleciona
        apenas os `SEARCH_K_FINAL` (ex: 3) melhores,
        garantindo alta precisão no contexto final enviado ao LLM.

---
### Métodos Principais
---

* **`__init__(self)`:**
    * Carrega o modelo de embedding (`EMBEDDING_MODEL_NAME`).
    * Carrega o `ChromaDB` do `VECTOR_DB_DIR`.
    * Carrega o modelo CrossEncoder (`RERANKER_MODEL_NAME`) na
        memória para a Etapa 2.

* **`retrieve_context_with_scores(self, query)`:**
    * Método principal que implementa o fluxo de "Etapa 1 + Etapa 2"
        (Recall + Re-Ranking).
    * Usado pelo `rag_chain.py` e pelo modo "COM Re-Ranking"
        do `validate_vector_db.py`.

* **`retrieve_context_vector_search_only(self, query)`:**
    * Executa *apenas* a Etapa 1 (Recall).
    * Busca diretamente os `SEARCH_K_FINAL` melhores
        resultados da busca vetorial pura.
    * Usado pelo `validate_vector_db.py` para o modo
        "SÓ Vetorial", permitindo uma comparação A/B direta
        da eficácia do Re-Ranker.

* **`get_all_chunks(self)`:**
    * Uma função utilitária que expõe o método `.get()`
        do ChromaDB, usada pelos scripts de validação para
        listar e exportar todo o conteúdo do banco de vetores.
"""


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
