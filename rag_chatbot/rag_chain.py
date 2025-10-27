# rag_chain.py
import os
import sqlite3
from typing import List, TypedDict

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import START, StateGraph

# Importar nossos módulos locais
import config
import database as history_db  # Importa o database.py (SQLite)
from vector_retriever import VectorRetriever

# Carregar variáveis de ambiente (necessário para a API Key)
load_dotenv()

# Garantir que o banco de dados de histórico exista
history_db.init_db()


class RAGState(TypedDict):
    """Define o estado do grafo LangGraph."""

    question: str
    context: List[Document]
    answer: str
    history: List[HumanMessage | AIMessage]


class RAGChain:
    """
    Orquestra o fluxo RAG usando LangGraph, integrando:
    1. VectorRetriever (Chroma + Re-Ranker)
    2. Google Gemini LLM
    3. Histórico do Chat (SQLite)
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

        # 1. Inicializar o LLM (usando config.py)
        self.model = ChatGoogleGenerativeAI(
            model=config.GEMINI_MODEL_NAME,
            api_key=config.GEMINI_API_KEY,
            temperature=0.0,
        )

        # 2. Inicializar nosso retriever com re-ranking
        self.retriever = VectorRetriever()

        # 3. Definir o prompt do sistema
        self.system_prompt = """Você é um assistente de IA especialista.
        Sua tarefa é responder à pergunta do usuário com base unicamente no contexto fornecido.
        Seja claro, conciso e use as informações dos documentos.
        Se a resposta não estiver no contexto, diga "Desculpe, não encontrei essa informação nos documentos fornecidos."
        Não use nenhum conhecimento prévio.
        Responda em português."""

        # 4. Construir o grafo (LangGraph)
        graph = StateGraph(RAGState)
        graph.add_node("load_history", self.load_history)
        graph.add_node("retrieve", self.retrieve)
        graph.add_node("generate", self.generate)

        graph.add_edge(START, "load_history")
        graph.add_edge("load_history", "retrieve")
        graph.add_edge("retrieve", "generate")

        self.graph = graph.compile()

    def _get_db_connection(self):
        """Helper para conectar ao banco SQLite."""
        return sqlite3.connect(history_db.DB_PATH)

    def load_history(self, state: RAGState) -> RAGState:
        """Carrega o histórico do chat do banco SQLite."""
        print(f"Carregando histórico para session_id: {self.session_id}")
        messages = []
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_message, bot_response
                FROM chat_history
                WHERE session_id = ?
                ORDER BY timestamp ASC
                """,
                (self.session_id,),
            )
            for row in cursor.fetchall():
                messages.append(HumanMessage(content=row[0]))
                messages.append(AIMessage(content=row[1]))
            conn.close()
        except Exception as e:
            print(f"Erro ao carregar histórico: {e}")

        return {"history": messages}

    def retrieve(self, state: RAGState) -> RAGState:
        """Recupera o contexto usando o VectorRetriever (com re-ranking)."""
        print("Recuperando contexto...")
        retrieved_docs = self.retriever.retrieve_context(state["question"])
        return {"context": retrieved_docs}

    def generate(self, state: RAGState) -> RAGState:
        """Gera a resposta usando a LLM e o contexto."""
        print("Gerando resposta...")
        docs_content = "\n\n--- Contexto ---\n\n".join(
            doc.page_content for doc in state["context"]
        )

        # Monta a lista de mensagens (Sistema + Histórico + Pergunta)
        messages = [SystemMessage(content=self.system_prompt)]
        messages.extend(state["history"])
        messages.append(
            HumanMessage(
                content=f"Contexto: {docs_content}\n\nPergunta: {state['question']}"
            )
        )

        try:
            response = self.model.invoke(messages)
            answer = response.content
            # Salva a interação no histórico
            self.save_message(state["question"], answer)
            return {"answer": answer}
        except Exception as e:
            print(f"Erro ao invocar LLM: {e}")
            return {"answer": "Ocorreu um erro ao processar sua solicitação."}

    def save_message(self, user_msg: str, bot_msg: str):
        """Salva a interação atual no banco SQLite."""
        print(f"Salvando mensagem para session_id: {self.session_id}")
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chat_history (session_id, user_message, bot_response)
                VALUES (?, ?, ?)
                """,
                (self.session_id, user_msg, bot_msg),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Erro ao salvar mensagem: {e}")

    def generate_response(self, question: str) -> str:
        """Ponto de entrada para o fluxo RAG."""
        initial_state = {
            "question": question,
            "context": [],
            "answer": "",
            "history": [],
        }
        # Invoca o grafo
        result = self.graph.invoke(initial_state)
        return result["answer"]

    def get_history_for_display(self) -> List[tuple]:
        """Busca o histórico formatado para exibição no Streamlit."""
        print(f"Buscando histórico de display para: {self.session_id}")
        history = []
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_message, bot_response
                FROM chat_history
                WHERE session_id = ?
                ORDER BY timestamp ASC
                """,
                (self.session_id,),
            )
            history = cursor.fetchall()
            conn.close()
        except Exception as e:
            print(f"Erro ao buscar histórico para display: {e}")

        return history
