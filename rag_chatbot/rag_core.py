# rag_core.py
import os
import config  # Importa nosso arquivo de configuração
from typing import List
from typing_extensions import TypedDict

# --- Novas Importações (Baseadas no llm.py) ---
from langgraph.graph import StateGraph, START
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage

# --- Importações Originais (Mantidas) ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder

# --- Verificação da Chave de API (Mantida) ---
if not config.GEMINI_API_KEY:
    raise EnvironmentError(
        "A variável de ambiente GEMINI_API_KEY não foi definida. "
        "Por favor, crie um arquivo .env e adicione sua chave."
    )


# ---
# NOVO: Definição do Estado do Grafo (baseado no llm.py)
# ---
class RagState(TypedDict):
    """
    Representa o estado do nosso grafo RAG.
    - question: A pergunta original do usuário.
    - context: A lista de documentos recuperados e re-rankeados.
    - answer: A resposta final gerada pelo LLM.
    """

    question: str
    context: List[Document]
    answer: str


# ---
# NOVO: Classe do Processador RAG (baseado no llm.py)
# ---
class RagProcessor:
    """
    Encapsula toda a lógica de RAG, incluindo carregamento de modelos
    e o fluxo do LangGraph.
    """

    def __init__(self):
        # 1. Carregar LLM (Gemini)
        print(f"Carregando LLM (Gemini Model: {config.GEMINI_MODEL_NAME})...")
        self.model = ChatGoogleGenerativeAI(
            model=config.GEMINI_MODEL_NAME,
            google_api_key=config.GEMINI_API_KEY,
            temperature=0.3,
            convert_system_message_to_human=True,
        )

        # 2. Carregar Modelo de Embedding (Bi-Encoder)
        print("Carregando modelo de embeddings (Recall)...")
        self.embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_NAME)

        # 3. Carregar Banco de Vetores (Chroma)
        print("Carregando banco de vetores (ChromaDB)...")
        self.vectorstore = Chroma(
            persist_directory=config.VECTOR_DB_DIR,
            embedding_function=self.embeddings,
        )

        # 4. Carregar Modelo de Re-Ranking (CrossEncoder)
        print(f"Carregando modelo de Re-Ranking ({config.RERANKER_MODEL_NAME})...")
        self.reranker = CrossEncoder(config.RERANKER_MODEL_NAME)
        print("Modelos de Re-Ranking carregado.")

        # 5. Definir o System Prompt (baseado no template original)
        self.system_prompt = """Use o contexto a seguir para responder à pergunta do usuário.
O contexto é uma coleção de trechos de texto recuperados de documentos.
Se você não sabe a resposta com base no contexto, apenas diga que não sabe. Não tente inventar uma resposta.
Mantenha a resposta concisa e útil.
Seja sempre educado e profissional."""

        # 6. Construir o Grafo (LangGraph)
        print("Construindo o grafo (LangGraph)...")
        self.graph = self._build_graph()
        print("Grafo compilado. Processador RAG pronto.")

    def _build_graph(self) -> StateGraph:
        """Constrói o fluxo do LangGraph."""
        graph = StateGraph(RagState)

        # Adiciona os nós (funções que executam o trabalho)
        graph.add_node("retrieve", self.retrieve)
        graph.add_node("generate", self.generate)

        # Adiciona as arestas (como o estado flui)
        graph.add_edge(START, "retrieve")  # Começa pela recuperação
        graph.add_edge("retrieve", "generate")  # Depois da recuperação, gera a resposta

        # Compila o grafo em um objeto executável
        return graph.compile()

    # --- NÓS DO GRAFO ---

    def retrieve(self, state: RagState) -> dict:
        """
        Nó de Recuperação (Retrieve): Executa a lógica de 2 estágios
        (Recall Vetorial + Re-Ranking com CrossEncoder).
        """
        print("Executando nó: retrieve")
        query = state["question"]

        # ETAPA 1: RECALL (Busca Vetorial Rápida)
        results_with_scores = self.vectorstore.similarity_search_with_score(
            query, k=config.SEARCH_K_RAW
        )

        if not results_with_scores:
            print("[Retriever] Nenhum documento encontrado.")
            return {"context": []}

        # ETAPA 2: RE-RANKING (CrossEncoder)
        pairs = [[query, doc.page_content] for doc, score in results_with_scores]

        try:
            rerank_scores = self.reranker.predict(pairs)
            reranked_results = list(zip(results_with_scores, rerank_scores))
            # Ordena pelos novos scores (MAIOR é MELHOR)
            reranked_results.sort(key=lambda x: x[1], reverse=True)

            # Pega o Top-K final
            top_k_documents = [
                doc
                for (doc, old_score), rerank_score in reranked_results[
                    : config.SEARCH_K_FINAL
                ]
            ]

            print(
                f"[Retriever] Buscou {len(results_with_scores)} chunks, re-rankeou para {len(top_k_documents)}."
            )
            return {"context": top_k_documents}

        except Exception as e:
            print(f"Erro durante o Re-Ranking: {e}")
            # Fallback: Retorna os melhores da busca vetorial
            print("Fallback: Retornando resultados da busca vetorial simples.")
            sorted_by_vector_score = sorted(results_with_scores, key=lambda x: x[1])
            fallback_docs = [
                doc for doc, score in sorted_by_vector_score[: config.SEARCH_K_FINAL]
            ]
            return {"context": fallback_docs}

    def generate(self, state: RagState) -> dict:
        """
        Nó de Geração (Generate): Pega o contexto e a pergunta,
        e gera uma resposta usando o LLM.
        """
        print("Executando nó: generate")
        question = state["question"]
        context = state["context"]

        if not context:
            print("[Generate] Nenhum contexto fornecido. Respondendo sem contexto.")
            docs_content = "Nenhum contexto encontrado."
        else:
            docs_content = "\n\n".join(doc.page_content for doc in context)

        # Cria as mensagens para o LLM (padrão do llm.py)
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"Contexto:\n{docs_content}\n\nPergunta: {question}"),
        ]

        response = self.model.invoke(messages)
        return {"answer": response.content}

    def get_response(self, question: str) -> (str, List[Document]):
        """
        Ponto de entrada principal para o app.py.
        Invoca o grafo e retorna a resposta e os documentos fonte.

        NOTA: Este fluxo (baseado no llm.py) NÃO usa histórico de chat.
        """
        initial_state = {"question": question, "context": [], "answer": ""}

        # Invoca o grafo
        final_state = self.graph.invoke(initial_state)

        return final_state["answer"], final_state["context"]


# --- Singleton Instance ---
# Cria uma instância global única do processador quando o módulo é importado.
# O app.py irá importar esta instância.

_rag_processor_instance = None


def get_rag_processor():
    """
    Inicializa e retorna a instância singleton do Processador RAG.
    """
    global _rag_processor_instance
    if _rag_processor_instance is None:
        print("Inicializando instância global do RagProcessor...")
        _rag_processor_instance = RagProcessor()
    return _rag_processor_instance
