# rag_chain.py
import os
import sqlite3
from typing import List, TypedDict, Optional
from datetime import datetime

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

    # Timestamps para métricas
    request_start_time: datetime
    retrieval_end_time: datetime

    # ID da mensagem de chat recém-criada
    new_message_id: Optional[int]


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
        )  #

        # 2. Inicializar nosso retriever com re-ranking
        self.retriever = VectorRetriever()  #

        # 3. Definir o prompt do sistema
        self.system_prompt = """<prompt_de_sistema>
<definicao_do_papel>
Você é um assistente virtual especialista no programa Quita Goiás, com foco em Transação Tributária. Sua identidade é a de um especialista prestativo e confiável.
</definicao_do_papel>
<instrucoes_principais>
Sua principal função é fornecer informações precisas, claras e detalhadas sobre o programa Quita Goiás, suas regras e procedimentos.
</instrucoes_principais>
<restricoes_de_conhecimento>
1.  **Restrição Absoluta de Conhecimento:** Você deve basear suas respostas *exclusivamente* nas informações fornecidas no contexto.
2.  **Proibição de Conhecimento Prévio:** É estritamente proibido usar qualquer conhecimento prévio ou informações externas ao contexto fornecido.
</restricoes_de_conhecimento>
<persona_e_estilo>
1.  **Tom:** Mantenha uma postura profissional, amigável, prestativa e de especialista.
2.  **Linguagem:** Responda em linguagem natural, fluente e utilizando a língua portuguesa do Brasil.
3.  **Clareza (Anti-Jargão):** Evite o uso de termos jurídicos ou complexos. Sempre priorize a forma mais simples e acessível de explicar os conceitos, pensando no contribuinte leigo.
4.  **Explicação de Termos:** Se for absolutamente obrigatório usar um termo jurídico ou técnico (que esteja no contexto), explique-o de forma simples imediatamente.
</persona_e_estilo>
<regras_situacionais>
    <regra>
        <condicao>
        Se a mensagem do usuário for *apenas* um cumprimento (exemplos: "Olá", "Oi", "Bom dia", "Tudo bem?").
        </condicao>
        <acao>
        Responda ao cumprimento de forma amigável e se apresente. Use este formato: "Olá! Eu sou um assistente virtual e estou pronto para tirar suas dúvidas sobre o programa Quita Goiás. Como posso ajudar?"
        </acao>
    </regra>
    <regra>
        <condicao>
        Se a resposta para a pergunta do usuário *não* estiver no contexto fornecido.
        </condicao>
        <acao>
        Responda *exatamente* com o seguinte texto, sem adicionar ou modificar nada: "Desculpe, não encontrei essa informação. Eu sou um assistente focado no programa Quita Goiás e só posso responder sobre os tópicos presentes nos documentos oficiais. Você poderia perguntar de outra forma sobre o programa?"
        </acao>
    </regra>
    <regra>
        <condicao>
        Para todas as outras perguntas sobre o programa Quita Goiás.
        </condicao>
        <acao>
        Forneça uma resposta precisa, clara e detalhada, baseando-se *apenas* nas informações do contexto.
        </acao>
    </regra>
</regras_situacionais>
</prompt_de_sistema>"""  #

        # 4. Construir o grafo (LangGraph)
        graph = StateGraph(RAGState)  #
        graph.add_node("load_history", self.load_history)  #
        graph.add_node("retrieve", self.retrieve)  #
        graph.add_node("generate", self.generate)  #

        graph.add_edge(START, "load_history")  #
        graph.add_edge("load_history", "retrieve")  #
        graph.add_edge("retrieve", "generate")  #

        self.graph = graph.compile()  #

    def _get_db_connection(self):
        """Helper para conectar ao banco SQLite."""
        return sqlite3.connect(history_db.DB_PATH)  #

    def load_history(self, state: RAGState) -> RAGState:
        """Carrega o histórico do chat do banco SQLite."""
        print(f"Carregando histórico para session_id: {self.session_id}")
        messages = []  #
        try:
            conn = self._get_db_connection()  #
            cursor = conn.cursor()  #
            cursor.execute(
                """
                SELECT user_message, bot_response
                FROM chat_history
                WHERE session_id = ?
                ORDER BY request_start_time ASC
                """,
                (self.session_id,),
            )  #
            for row in cursor.fetchall():  #
                messages.append(HumanMessage(content=row[0]))  #
                messages.append(AIMessage(content=row[1]))  #
            conn.close()  #
        except Exception as e:
            print(f"Erro ao carregar histórico: {e}")  #

        # Passa o request_start_time para os próximos nós
        return {
            "history": messages,
            "request_start_time": state["request_start_time"],
            "new_message_id": None,  # Garante que seja None no início
        }  #

    def retrieve(self, state: RAGState) -> RAGState:
        """Recupera o contexto usando o VectorRetriever (com re-ranking)."""
        print("Recuperando contexto...")
        retrieved_docs = self.retriever.retrieve_context(state["question"])  #

        # Captura o timestamp de fim da recuperação
        retrieval_end_time = datetime.now()  #

        return {"context": retrieved_docs, "retrieval_end_time": retrieval_end_time}  #

    def generate(self, state: RAGState) -> RAGState:
        """Gera a resposta usando a LLM e o contexto."""
        print("Gerando resposta...")

        # Obter timestamps do estado
        request_start_time = state["request_start_time"]  #
        retrieval_end_time = state["retrieval_end_time"]  #

        user_msg = state["question"]  #
        user_chars = len(user_msg)  #

        docs_content = "\n\n--- Contexto ---\n\n".join(
            doc.page_content for doc in state["context"]
        )  #

        # Monta a lista de mensagens
        messages = [SystemMessage(content=self.system_prompt)]  #
        messages.extend(state["history"])  #
        messages.append(
            HumanMessage(content=f"Contexto: {docs_content}\n\nPergunta: {user_msg}")
        )  #

        try:
            response = self.model.invoke(messages)  #

            # Captura o timestamp final
            response_end_time = datetime.now()  #

            # --- Cálculo de Métricas ---
            answer = response.content  #
            bot_chars = len(answer)  #

            # Calcula durações
            retrieval_duration_sec = (
                retrieval_end_time - request_start_time
            ).total_seconds()  #
            generation_duration_sec = (
                response_end_time - retrieval_end_time
            ).total_seconds()  #
            total_duration_sec = (
                response_end_time - request_start_time
            ).total_seconds()  #

            # --- INÍCIO DA CORREÇÃO ---
            # Extrai tokens
            user_tokens = 0  # Tokens do prompt
            bot_tokens = 0  # Tokens da resposta

            if response.response_metadata:  #
                # A chave correta para o Gemini é 'usage_metadata'
                usage_metadata = response.response_metadata.get("usage_metadata", {})

                # As chaves corretas são 'prompt_token_count' e 'candidates_token_count'
                user_tokens = usage_metadata.get("prompt_token_count", 0)
                bot_tokens = usage_metadata.get("candidates_token_count", 0)
            # --- FIM DA CORREÇÃO ---

            # Salva a interação no histórico com os novos dados
            new_message_id = self.save_message(
                user_msg,
                answer,
                user_chars,
                bot_chars,
                user_tokens,
                bot_tokens,
                request_start_time,
                retrieval_end_time,
                response_end_time,
                retrieval_duration_sec,
                generation_duration_sec,
                total_duration_sec,
            )  #

            return {"answer": answer, "new_message_id": new_message_id}  #
        except Exception as e:
            print(f"Erro ao invocar LLM: {e}")  #
            return {"answer": "Ocorreu um erro ao processar sua solicitação."}  #

    # --- FUNÇÃO SAVE_MESSAGE ATUALIZADA PARA RETORNAR O ID ---
    def save_message(
        self,
        user_msg: str,
        bot_msg: str,
        user_chars: int,
        bot_chars: int,
        user_tokens: int,
        bot_tokens: int,
        request_start_time: datetime,
        retrieval_end_time: datetime,
        response_end_time: datetime,
        retrieval_duration_sec: float,
        generation_duration_sec: float,
        total_duration_sec: float,
    ) -> Optional[int]:
        """Salva a interação atual no banco SQLite e retorna o ID da nova linha."""
        print(f"Salvando mensagem para session_id: {self.session_id}")
        new_id = None  #
        try:
            conn = self._get_db_connection()  #
            cursor = conn.cursor()  #
            cursor.execute(
                """
                INSERT INTO chat_history (
                    session_id, user_message, bot_response, 
                    user_chars, bot_chars, 
                    user_tokens, bot_tokens, 
                    request_start_time, retrieval_end_time, response_end_time,
                    retrieval_duration_sec, generation_duration_sec, total_duration_sec
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.session_id,
                    user_msg,
                    bot_msg,
                    user_chars,
                    bot_chars,
                    user_tokens,
                    bot_tokens,
                    request_start_time,
                    retrieval_end_time,
                    response_end_time,
                    retrieval_duration_sec,
                    generation_duration_sec,
                    total_duration_sec,
                ),
            )  #
            # --- Captura o ID da linha recém-inserida ---
            new_id = cursor.lastrowid  #

            conn.commit()  #
            conn.close()  #

        except Exception as e:
            print(f"Erro ao salvar mensagem: {e}")  #

        return new_id  # Retorna o ID

    def generate_response(self, question: str) -> dict:
        """
        Ponto de entrada para o fluxo RAG.
        Retorna um dicionário com a resposta e o ID da mensagem.
        """

        # Captura o timestamp inicial aqui
        request_start_time = datetime.now()  #

        initial_state = {
            "question": question,
            "context": [],
            "answer": "",
            "history": [],
            "request_start_time": request_start_time,  # Passa para o estado
            "retrieval_end_time": request_start_time,  # Inicializa (será sobrescrito)
            "new_message_id": None,  # Inicializa
        }  #
        # Invoca o grafo
        result = self.graph.invoke(initial_state)  #

        # Retorna o dicionário completo
        return {"answer": result["answer"], "message_id": result["new_message_id"]}  #

    def get_history_for_display(self) -> List[tuple]:
        """
        Busca o histórico formatado para exibição no Streamlit,
        incluindo o ID da mensagem e o feedback existente.
        """
        print(f"Buscando histórico de display para: {self.session_id}")
        history = []  #
        try:
            conn = self._get_db_connection()  #
            cursor = conn.cursor()  #
            # Query ATUALIZADA com LEFT JOIN na tabela feedback
            cursor.execute(
                """
                SELECT 
                    h.id, 
                    h.user_message, 
                    h.bot_response, 
                    f.rating
                FROM chat_history h
                LEFT JOIN feedback f ON h.id = f.message_id
                WHERE h.session_id = ?
                ORDER BY h.request_start_time ASC
                """,
                (self.session_id,),
            )  #
            history = cursor.fetchall()  #
            conn.close()  #
        except Exception as e:
            print(f"Erro ao buscar histórico para display: {e}")  #

        return history  #

    def save_feedback(self, message_id: int, rating: str, comment: str = None):
        """Salva o feedback do usuário no banco de dados."""
        print(f"Salvando feedback para message_id: {message_id} (Rating: {rating})")
        try:
            conn = self._get_db_connection()  #
            cursor = conn.cursor()  #

            # Use INSERT OR REPLACE para permitir que o usuário mude de ideia
            # (ou apenas INSERT se preferir que o primeiro clique seja final)
            cursor.execute(
                """
                INSERT INTO feedback (message_id, rating, comment)
                VALUES (?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                rating = excluded.rating,
                comment = excluded.comment,
                timestamp = CURRENT_TIMESTAMP
                """,
                (message_id, rating, comment),
            )  #
            conn.commit()  #
            conn.close()  #
            print("Feedback salvo com sucesso.")
        except Exception as e:
            print(f"Erro ao salvar feedback: {e}")  #
