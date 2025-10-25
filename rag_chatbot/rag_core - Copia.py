# rag_core.py
import os

# --- Importações de Configuração e Utilitários ---
import config  # Importa nosso novo arquivo de configuração
from typing import List

# --- Importações do LangChain (Atualizadas para LCEL) ---
# CORRIGIDO: Substituindo a cadeia antiga pelas funções de construção LCEL
from langchain.chains import create_retrieval_chain, create_history_aware_retriever

# CORRIGIDO: Importando a função para combinar documentos
from langchain.chains.combine_documents import create_stuff_documents_chain

# CORRIGIDO: Usando ChatPromptTemplate e MessagesPlaceholder para prompts modernos
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# --- Novos Imports para LLM (Gemini) e Retriever ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun

# --- NOVO IMPORT: Para o Re-Ranking (CrossEncoder) ---
from sentence_transformers import CrossEncoder

# --- Verificação da Chave de API ---
if not config.GEMINI_API_KEY:
    raise EnvironmentError(
        "A variável de ambiente GEMINI_API_KEY não foi definida. "
        "Por favor, crie um arquivo .env e adicione sua chave."
    )

# --- Template de Prompt (Inalterado) ---
# Este template string agora será usado por um ChatPromptTemplate
CUSTOM_PROMPT_TEMPLATE = """
Use o contexto a seguir para responder à pergunta do usuário.
O contexto é uma coleção de trechos de texto recuperados de documentos.
Se você não sabe a resposta com base no contexto, apenas diga que não sabe. Não tente inventar uma resposta.
Mantenha a resposta concisa e útil.
Seja sempre educado e profissional.

Contexto:
{context}

Histórico da Conversa:
{chat_history}

Pergunta do Usuário: {question}
Resposta:
"""


# ---
# ALTERAÇÃO 1: Implementação do Retriever com RE-RANKING (CrossEncoder)
# (Esta classe permanece inalterada)
# ---
class ReRankingRetriever(BaseRetriever):
    """
    Um retriever personalizado que:
    1. Busca k_raw documentos (Recall) usando similaridade vetorial.
    2. Re-rankeia esses documentos (Precision) usando um modelo CrossEncoder.
    3. Retorna os k_final melhores documentos.
    """

    vectorstore: Chroma
    reranker: CrossEncoder  # <<< ATRIBUTO ADICIONADO
    k_raw: int = config.SEARCH_K_RAW
    k_final: int = config.SEARCH_K_FINAL

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """Executa a lógica de busca e re-ranking."""

        # ETAPA 1: RECALL (Busca Vetorial Rápida)
        # Busca os K_RAW resultados mais próximos com score
        results_with_scores = self.vectorstore.similarity_search_with_score(
            query, k=self.k_raw
        )

        if not results_with_scores:
            return []

        # ETAPA 2: RE-RANKING (CrossEncoder)

        # 1. Criar pares de [pergunta, chunk] para o Re-Ranker
        pairs = [[query, doc.page_content] for doc, score in results_with_scores]

        try:
            # 2. Obter os novos scores do Re-Ranker
            rerank_scores = self.reranker.predict(pairs)

            # 3. Combinar os documentos originais (com metadados) com seus novos scores
            # (doc, old_score) vem de results_with_scores
            reranked_results = list(zip(results_with_scores, rerank_scores))

            # 4. Ordenar pelos novos scores do Re-Ranker (MAIOR é MELHOR)
            reranked_results.sort(key=lambda x: x[1], reverse=True)

            # 5. Pegar o Top-K final (apenas os documentos)
            top_k_documents = [
                doc
                for (doc, old_score), rerank_score in reranked_results[: self.k_final]
            ]

            print(
                f"[Retriever] Buscou {len(results_with_scores)} chunks, "
                f"re-rankeou e selecionou os {len(top_k_documents)} melhores."
            )

            return top_k_documents

        except Exception as e:
            print(f"Erro durante o Re-Ranking: {e}")
            # Fallback: Se o Re-Ranker falhar, retorne os melhores da busca vetorial
            # (Lógica antiga: ordena por score L2, MENOR é MELHOR)
            print("Fallback: Retornando resultados da busca vetorial simples.")
            sorted_by_vector_score = sorted(results_with_scores, key=lambda x: x[1])
            return [doc for doc, score in sorted_by_vector_score[: self.k_final]]


# Variável global para carregar o chain apenas uma vez
rag_chain = None


def get_rag_chain():
    """
    Inicializa e retorna a cadeia RAG (agora usando LCEL).
    Carrega LLM, Embeddings, VectorStore e o modelo de Re-Ranking.
    Esta função NÃO gerencia mais a memória; isso deve ser feito pelo chamador (app.py).
    """
    global rag_chain
    if rag_chain:
        return rag_chain

    print("Carregando modelo de embeddings...")
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_NAME)

    print("Carregando banco de vetores...")
    vectordb = Chroma(
        persist_directory=config.VECTOR_DB_DIR, embedding_function=embeddings
    )

    # ---
    # ALTERAÇÃO 2: Carregar o modelo de Re-Ranking (CrossEncoder)
    # ---
    print(f"Carregando modelo de Re-Ranking ({config.RERANKER_MODEL_NAME})...")
    try:
        reranker = CrossEncoder(config.RERANKER_MODEL_NAME)
    except AttributeError:
        print("--- ERRO CRÍTICO ---")
        print("A variável 'RERANKER_MODEL_NAME' não foi encontrada em config.py.")
        print("Por favor, adicione-a ao seu arquivo config.py.")
        print("Exemplo: RERANKER_MODEL_NAME = 'ms-marco-MiniLM-L-6-v2'")
        print("--------------------")
        raise
    except Exception as e:
        print(f"Erro ao carregar o CrossEncoder: {e}")
        raise
    print("Modelo de Re-Ranking carregado.")

    # ---
    # ALTERAÇÃO 3: Substituição do LLM (Inalterado)
    # ---
    print(f"Carregando LLM (Gemini Model: {config.GEMINI_MODEL_NAME})...")
    llm = ChatGoogleGenerativeAI(
        model=config.GEMINI_MODEL_NAME,
        google_api_key=config.GEMINI_API_KEY,
        temperature=0.3,  # Baixa temperatura para respostas mais factuais
        convert_system_message_to_human=True,  # Necessário para alguns prompts
    )

    # ---
    # ALTERAÇÃO 4: Passar o Re-Ranker para o Retriever (Inalterado)
    # ---
    print(
        f"Inicializando Retriever com RE-RANKER (k_raw={config.SEARCH_K_RAW}, k_final={config.SEARCH_K_FINAL})..."
    )
    retriever = ReRankingRetriever(
        vectorstore=vectordb,
        reranker=reranker,  # <<< Passando o modelo de re-ranking carregado
    )

    # ---
    # ALTERAÇÃO 5: Construção da Cadeia RAG com LCEL
    # ---

    # 1. Novo Prompt para o History-Aware Retriever (Condensação da Pergunta)
    # Este prompt transforma o histórico e a nova pergunta em uma query de busca independente
    print("Criando prompt de condensação de pergunta...")
    condense_q_system_prompt = """Dada uma conversa e uma pergunta subsequente, reformule a pergunta subsequente para ser uma pergunta independente, no mesmo idioma da pergunta original.
Se a pergunta já for independente, apenas a retorne."""

    condense_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", condense_q_system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ]
    )

    # 2. Criar o History-Aware Retriever
    # Este retriever usará o LLM para condensar a pergunta antes de buscar no vectorstore
    print("Criando o history-aware retriever...")
    history_aware_retriever = create_history_aware_retriever(
        llm=llm,
        retriever=retriever,  # Nosso retriever customizado com ReRanking
        prompt=condense_q_prompt,
    )

    # 3. Novo Prompt de Resposta (usando o template string antigo)
    # Este prompt formatará os documentos recuperados e a pergunta para o LLM responder
    print("Criando prompt de resposta...")
    answer_prompt = ChatPromptTemplate.from_template(CUSTOM_PROMPT_TEMPLATE)

    # 4. Criar a "Document Chain"
    # Esta é a parte que efetivamente combina os documentos em uma resposta
    print("Criando a document chain...")
    document_chain = create_stuff_documents_chain(llm=llm, prompt=answer_prompt)

    # 5. Criar a Cadeia de Retrieval Final (a que o usuário pediu)
    # Esta cadeia primeiro executa o history_aware_retriever (obtendo documentos)
    # e depois passa os documentos e a entrada original para a document_chain
    print("Criando a cadeia de retrieval final (LCEL)...")
    rag_chain = create_retrieval_chain(
        retriever=history_aware_retriever,
        combine_docs_chain=document_chain,
    )

    print("Cadeia RAG (LCEL) pronta.")
    return rag_chain
