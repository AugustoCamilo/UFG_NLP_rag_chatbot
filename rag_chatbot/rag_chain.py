# rag_chain.py
import asyncio
from datetime import datetime
from typing import List, TypedDict, Optional

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import START, StateGraph
from sqlmodel import select

# Importações Locais
from settings import settings
import database
from database import ChatHistory, Feedback
from vector_retriever import VectorRetriever

# Carregar variáveis de ambiente
load_dotenv()


class RAGState(TypedDict):
    """Define o estado do grafo LangGraph."""

    question: str
    context: List[Document]
    answer: str
    history: List[HumanMessage | AIMessage]
    request_start_time: datetime
    retrieval_end_time: datetime
    new_message_id: Optional[int]
    is_synthetic: bool


class RAGChain:
    """
    Orquestrador RAG Async com persistência via SQLModel/SQLAlchemy.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

        # 1. Inicializar LLM (Gemini)
        self.model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL_NAME,
            api_key=settings.GEMINI_API_KEY,
            temperature=0.0,
        )

        # 2. Retriever (Síncrono)
        self.retriever = VectorRetriever()

        # 3. Prompt do Sistema
        self.system_prompt = """## Identidade e Objetivo
Você é o **Assistente Virtual Especialista no Programa Quita Goiás**.
Sua função é atuar como um especialista em Transação Tributária, prestando suporte confiável, seguro e extremamente didático aos contribuintes.

**Data atual do sistema:** {{DATA_ATUAL}}

## Contexto de Conhecimento (Fonte da Verdade)
Você deve responder às perguntas baseando-se **exclusivamente** nas informações contidas nas tags `<documentos_oficiais>` abaixo.
Ignore qualquer conhecimento externo sobre leis que não esteja explícito aqui, para evitar alucinações sobre prazos ou regras antigas.

<documentos_oficiais>
{{INSERIR_CONTEXTO_AQUI}}
</documentos_oficiais>

## Diretrizes de Comportamento (Persona)
1. **Tom de Voz:** Profissional, empático e especialista. Transmita segurança.
2. **Didática (Crucial):** O contexto fornecido pode conter linguagem jurídica ("juridiquês"). Sua tarefa é **traduzir** isso para o Português simples.
   * *Permissão:* Você pode usar seu conhecimento de língua portuguesa para reformular e simplificar explicações.
   * *Restrição:* Você **NÃO** pode alterar datas, valores, percentuais ou regras factuais.
3. **Explicação de Termos:** Se usar um termo técnico (ex: "Dívida Ativa"), explique o que significa logo em seguida, de forma breve.

## Gerenciamento da Conversa
Use o histórico fornecido para manter o contexto (ex: entender referências como "e qual é o prazo disso?").
   * **Regra de Prioridade:** A informação dentro de `<documentos_oficiais>` sempre prevalece sobre o histórico ou conhecimento prévio.

## Protocolos de Resposta (Chain of Thought)

### Passo 1: Verificação de Disponibilidade
Antes de responder, verifique se a resposta para a dúvida do usuário consta explicitamente em `<documentos_oficiais>`.
   * **Se NÃO constar:** Responda: "Desculpe, não encontrei essa informação específica nos documentos oficiais do Programa Quita Goiás aos quais tenho acesso. Sou um assistente focado estritamente nas regras atuais do programa. Poderia reformular sua pergunta?"
   * **Se constar:** Prossiga para o Passo 2.

### Passo 2: Construção da Resposta
1. **Cenário: Saudação Pura** (Ex: "Olá", "Bom dia")
   * Resposta: "Olá! Sou o assistente virtual do Quita Goiás. Estou aqui para tirar suas dúvidas sobre o programa de regularização fiscal. Como posso ajudar?"
2. **Cenário: Saudação + Pergunta** (Ex: "Oi, como parcelo?")
   * Ação: Ignore a saudação formal e responda diretamente à dúvida de forma cordial.
   * Resposta: "Olá! Para realizar o parcelamento, as regras são..." (Seguir contexto).
3. **Cenário: Dúvida Específica**
   * Resposta: Forneça a informação extraída do contexto, simplificando a linguagem conforme as diretrizes de didática.

## Regras de Segurança (Safety Rails)
* **Alucinação Zero:** Jamais invente datas, leis ou procedimentos não listados.
* **Formatação:** Use Markdown para facilitar a leitura (listas com marcadores, negrito para prazos e valores importantes).
Evite blocos de texto densos.
"""

        # 4. Construir o Grafo
        graph = StateGraph(RAGState)
        graph.add_node("load_history", self.load_history)
        graph.add_node("retrieve", self.retrieve)
        graph.add_node("generate", self.generate)

        graph.add_edge(START, "load_history")
        graph.add_edge("load_history", "retrieve")
        graph.add_edge("retrieve", "generate")

        self.graph = graph.compile()

    # --- Nós do Grafo (Async) ---

    async def load_history(self, state: RAGState) -> RAGState:
        """Carrega o histórico do banco de forma assíncrona."""
        messages = []

        async with database.AsyncSessionFactory() as session:
            statement = (
                select(ChatHistory)
                .where(ChatHistory.session_id == self.session_id)
                .order_by(ChatHistory.request_start_time)
            )
            result = await session.execute(statement)
            history_records = result.scalars().all()

            for record in history_records:
                messages.append(HumanMessage(content=record.user_message))
                messages.append(AIMessage(content=record.bot_response))

        return {
            "history": messages,
            "request_start_time": state["request_start_time"],
            "new_message_id": None,
            "is_synthetic": state.get("is_synthetic", False),  # Mantém o estado
        }

    async def retrieve(self, state: RAGState) -> RAGState:
        """Recupera contexto."""
        question = state["question"]

        # Executa operação bloqueante em thread separada
        retrieved_docs = await asyncio.to_thread(
            self.retriever.retrieve_context, question
        )

        return {"context": retrieved_docs, "retrieval_end_time": datetime.now()}

    async def generate(self, state: RAGState) -> RAGState:
        """Gera resposta e salva no banco."""

        # Timestamps
        request_start_time = state["request_start_time"]
        retrieval_end_time = state["retrieval_end_time"]
        is_synthetic = state.get("is_synthetic", False)

        user_msg = state["question"]
        docs_content = "\n\n".join(doc.page_content for doc in state["context"])

        # Preparar Prompt
        current_date = datetime.now().strftime("%d/%m/%Y")
        final_system_prompt = self.system_prompt.replace(
            "{{INSERIR_CONTEXTO_AQUI}}", docs_content
        ).replace("{{DATA_ATUAL}}", current_date)

        messages = [SystemMessage(content=final_system_prompt)]
        messages.extend(state["history"])
        messages.append(HumanMessage(content=user_msg))

        # Contagem de Tokens
        try:
            user_tokens = self.model.get_num_tokens_from_messages(messages)
        except:
            user_tokens = 0

        # Chamada Async ao LLM
        try:
            response = await self.model.ainvoke(messages)
            answer = response.content
            response_end_time = datetime.now()
        except Exception as e:
            return {"answer": f"Erro técnico: {str(e)}", "new_message_id": None}

        # Métricas
        try:
            bot_tokens = self.model.get_num_tokens(answer)
        except:
            bot_tokens = 0

        # Salvar no Banco (Async)
        new_message_id = await self.save_message_async(
            user_msg=user_msg,
            bot_msg=answer,
            is_synthetic=is_synthetic,  # Passando a flag
            metrics={
                "user_chars": len(user_msg),
                "bot_chars": len(answer),
                "user_tokens": user_tokens,
                "bot_tokens": bot_tokens,
                "request_start_time": request_start_time,
                "retrieval_end_time": retrieval_end_time,
                "response_end_time": response_end_time,
            },
        )

        return {"answer": answer, "new_message_id": new_message_id}

    # --- Métodos Auxiliares (Async) ---

    async def save_message_async(
        self, user_msg: str, bot_msg: str, is_synthetic: bool, metrics: dict
    ) -> int:
        """Persiste a interação usando SQLModel."""

        # Calcular durações
        req_start = metrics["request_start_time"]
        ret_end = metrics["retrieval_end_time"]
        res_end = metrics["response_end_time"]

        chat_entry = ChatHistory(
            session_id=self.session_id,
            user_message=user_msg,
            bot_response=bot_msg,
            is_synthetic=is_synthetic,  # Salva no banco
            user_chars=metrics["user_chars"],
            bot_chars=metrics["bot_chars"],
            user_tokens=metrics["user_tokens"],
            bot_tokens=metrics["bot_tokens"],
            request_start_time=req_start,
            retrieval_end_time=ret_end,
            response_end_time=res_end,
            retrieval_duration_sec=(ret_end - req_start).total_seconds(),
            generation_duration_sec=(res_end - ret_end).total_seconds(),
            total_duration_sec=(res_end - req_start).total_seconds(),
        )

        async with database.AsyncSessionFactory() as session:
            session.add(chat_entry)
            await session.commit()
            await session.refresh(chat_entry)
            return chat_entry.id

    async def generate_response(
        self, question: str, is_synthetic: bool = False
    ) -> dict:
        """
        Ponto de entrada PÚBLICO e ASYNC.
        Aceita o parâmetro is_synthetic.
        """
        initial_state = {
            "question": question,
            "context": [],
            "answer": "",
            "history": [],
            "request_start_time": datetime.now(),
            "retrieval_end_time": datetime.now(),
            "new_message_id": None,
            "is_synthetic": is_synthetic,  # Injeta no estado inicial
        }

        result = await self.graph.ainvoke(initial_state)

        return {"answer": result["answer"], "message_id": result["new_message_id"]}

    async def get_history_for_display(self) -> List[tuple]:
        """Retorna o histórico para a UI (Streamlit)."""
        async with database.AsyncSessionFactory() as session:
            query = (
                select(ChatHistory, Feedback.rating)
                .outerjoin(Feedback, ChatHistory.id == Feedback.message_id)
                .where(ChatHistory.session_id == self.session_id)
                .order_by(ChatHistory.request_start_time)
            )

            result = await session.execute(query)
            formatted_history = []
            for history, rating in result.all():
                formatted_history.append(
                    (history.id, history.user_message, history.bot_response, rating)
                )

            return formatted_history

    async def save_feedback(self, message_id: int, rating: str, comment: str = None):
        """Salva ou atualiza feedback."""
        async with database.AsyncSessionFactory() as session:
            statement = select(Feedback).where(Feedback.message_id == message_id)
            result = await session.execute(statement)
            existing_feedback = result.scalars().first()

            if existing_feedback:
                existing_feedback.rating = rating
                existing_feedback.comment = comment
                existing_feedback.timestamp = datetime.now()
                session.add(existing_feedback)
            else:
                new_feedback = Feedback(
                    message_id=message_id, rating=rating, comment=comment
                )
                session.add(new_feedback)

            await session.commit()
