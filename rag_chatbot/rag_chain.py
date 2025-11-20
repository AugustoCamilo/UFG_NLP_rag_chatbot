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

    ---
    ### Arquitetura e Gerenciamento de Estado (Histórico da Conversa)

    Esta classe implementa um RAG **Stateful** (com memória). O contexto da
    conversa é mantido através de um banco de dados SQLite (`chat_solution.db`),
    garantindo que o LLM considere as interações passadas ao formular
    uma nova resposta.

    **O fluxo de manutenção do histórico por `session_id` ocorre da seguinte forma:**

    1.  **Carregamento (Nó `load_history`):**
        * Quando uma nova pergunta é recebida (`generate_response`), o `LangGraph`
            inicia no nó `load_history`.
        * Este nó consulta a tabela `chat_history` no `chat_solution.db`
            buscando *todas* as entradas (`user_message`, `bot_response`)
            associadas ao `session_id` do usuário.
        * As interações passadas são formatadas como objetos `HumanMessage` e
            `AIMessage` e armazenadas no estado (`state["history"]`).

    2.  **Geração (Nó `generate`):**
        * O nó `generate` recebe o estado, que agora contém o
            histórico completo da sessão.
        * Ele monta o prompt final para o LLM na seguinte ordem:
            1.  `SystemMessage` (O prompt do sistema/persona)
            2.  `state["history"]` (O histórico completo da conversa)
            3.  `HumanMessage` (O contexto RAG [chunks] + a nova pergunta)
        * O LLM (`self.model.invoke`) recebe, assim, o contexto completo
            do diálogo.

    3.  **Persistência (Função `save_message`):**
        * Após o LLM gerar a resposta (`answer`), a função `generate`
            chama `self.save_message`.
        * Esta função insere a nova interação (pergunta atual + resposta
            do bot) na tabela `chat_history`, associada ao `session_id`,
            garantindo que ela seja carregada na próxima rodada.
    ---
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
        self.system_prompt = """## Identidade e Objetivo
Você é o **Assistente Virtual Especialista no Programa Quita Goiás**.
Sua função é atuar como um especialista em Transação Tributária, prestando suporte confiável, seguro e extremamente didático aos contribuintes.

**Data atual do sistema:** {{DATA_ATUAL}}

## Contexto de Conhecimento (Fonte da Verdade)
Você deve responder às perguntas baseando-se **exclusivamente** nas informações contidas nas tags `<documentos_oficiais>` abaixo. Ignore qualquer conhecimento externo sobre leis que não esteja explícito aqui, para evitar alucinações sobre prazos ou regras antigas.

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
* **Formatação:** Use Markdown para facilitar a leitura (listas com marcadores, negrito para prazos e valores importantes). Evite blocos de texto densos."""

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
        request_start_time = state["request_start_time"]
        retrieval_end_time = state["retrieval_end_time"]

        user_msg = state["question"]
        user_chars = len(user_msg)

        # 1. Formatar o Contexto a partir dos documentos recuperados
        docs_content = "\n\n".join(doc.page_content for doc in state["context"])

        # 2. Injetar Contexto e Data no System Prompt
        # Obtém a data atual para ajudar em perguntas sobre prazos/validade
        current_date = datetime.now().strftime("%d/%m/%Y")

        # Substitui os placeholders definidos no prompt do sistema
        # Se os placeholders não existirem no prompt, o texto permanece inalterado
        final_system_prompt = self.system_prompt.replace(
            "{{INSERIR_CONTEXTO_AQUI}}", docs_content
        ).replace("{{DATA_ATUAL}}", current_date)

        # 3. Montar a lista de mensagens
        # O SystemMessage agora carrega o contexto "cheio" e as regras
        messages = [SystemMessage(content=final_system_prompt)]

        # Adiciona o histórico da conversa (Memória de curto prazo)
        messages.extend(state["history"])

        # A mensagem do usuário vai LIMPA (sem repetir o contexto),
        # o que economiza tokens e evita confusão semântica
        messages.append(HumanMessage(content=user_msg))

        # 4. Calcular tokens do prompt (Entrada)
        try:
            user_tokens = self.model.get_num_tokens_from_messages(messages)
        except Exception as e:
            print(f"Aviso: Falha ao calcular tokens do prompt: {e}")
            user_tokens = 0  # Define como 0 se a contagem falhar

        try:
            # 5. Invocar o Modelo
            response = self.model.invoke(messages)

            # Captura o timestamp final
            response_end_time = datetime.now()

            # --- Cálculo de Métricas ---
            answer = response.content
            bot_chars = len(answer)

            # Calcula durações
            retrieval_duration_sec = (
                retrieval_end_time - request_start_time
            ).total_seconds()
            generation_duration_sec = (
                response_end_time - retrieval_end_time
            ).total_seconds()
            total_duration_sec = (
                response_end_time - request_start_time
            ).total_seconds()

            # 6. Calcular tokens da resposta (Saída)
            try:
                bot_tokens = self.model.get_num_tokens(answer)
            except Exception as e:
                print(f"Aviso: Falha ao calcular tokens da resposta: {e}")
                bot_tokens = 0  # Define como 0 se a contagem falhar

            # 7. Salvar a interação no histórico
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
            )

            # Retorna o resultado para o grafo
            return {"answer": answer, "new_message_id": new_message_id}

        except Exception as e:
            print(f"Erro ao invocar LLM: {e}")
            # Retorno de fallback em caso de erro na API
            return {
                "answer": "Desculpe, ocorreu um erro técnico ao processar sua solicitação. Por favor, tente novamente."
            }

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
