# app.py
"""
Ponto de Entrada Principal (Frontend) da Aplicação de Chat RAG.

Atualizado para consumir a arquitetura ASYNC do RAGChain e SQLModel.
"""

import streamlit as st
import uuid
import asyncio
import os
from streamlit.components.v1 import html
from rag_chain import RAGChain


# --- FUNÇÃO PARA FOCAR O INPUT ---
def set_focus():
    """
    Injeta JavaScript para focar automaticamente a caixa de chat_input.
    """
    script = """
    <script>
    setTimeout(function() {
        var input = document.querySelector('[data-testid="stChatInput"] textarea');
        if (input) {
            input.focus();
        }
    }, 100);
    </script>
    """
    html(script, height=0)


# --- FUNÇÃO DE CALLBACK (ADAPTADA PARA ASYNC) ---
def handle_feedback(chain_instance, message_id, rating):
    """
    Chamada quando um botão de feedback (like/dislike) é clicado.
    Agora usa asyncio.run() para chamar o método async do backend.
    """
    # Bridge Sync -> Async para o callback
    asyncio.run(chain_instance.save_feedback(message_id, rating))

    # Atualiza o estado da sessão para desabilitar os botões
    st.session_state.feedback[message_id] = rating
    st.toast("Obrigado pelo seu feedback!", icon="👍")


# --- FUNÇÃO PARA EXIBIR OS BOTÕES ---
def display_feedback_buttons(chain_instance, message_id, existing_rating=None):
    """
    Exibe os botões de like/dislike (👍/👎) para uma determinada mensagem.
    """
    feedback_given = existing_rating or st.session_state.feedback.get(message_id)

    col1, col2, rest = st.columns([1, 1, 10])

    with col1:
        st.button(
            "👍",
            key=f"like_{message_id}",
            on_click=handle_feedback,
            args=(chain_instance, message_id, "like"),
            disabled=(feedback_given is not None),
        )

    with col2:
        st.button(
            "👎",
            key=f"dislike_{message_id}",
            on_click=handle_feedback,
            args=(chain_instance, message_id, "dislike"),
            disabled=(feedback_given is not None),
        )


# --- Ponto de Entrada Principal ---

st.set_page_config(page_title="Programa Quita Goiás", page_icon="🤖")
st.title("Programa Quita Goiás")
st.caption("Processamento em Linguagem Natural - Turma 2 - Grupo 25")

# 1. Gerenciar o ID da Sessão
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    # print(f"Nova sessão criada: {st.session_state.session_id}")

# Inicializa o estado de feedback
if "feedback" not in st.session_state:
    st.session_state.feedback = {}

# 2. Inicializar o RAGChain
try:
    # A inicialização (__init__) do RAGChain ainda é síncrona, então ok.
    chain = RAGChain(st.session_state.session_id)
except FileNotFoundError as e:
    st.error(f"Erro: Banco de vetores não encontrado em '{e}'.")
    st.error("Execute 'python ingest.py' antes de iniciar o aplicativo.")
    st.stop()
except Exception as e:
    st.error(f"Erro ao inicializar a RAG Chain: {e}")
    st.stop()

# Botão de Sair na Barra Lateral
with st.sidebar:
    st.header("Controle da Aplicação")
    st.warning("Clicar em 'Sair' encerrará o servidor do Streamlit.")
    if st.button("Sair e Encerrar Aplicação"):
        print("Botão 'Sair' clicado. Encerrando o processo do servidor.")
        os._exit(0)


# 3. Exibir o histórico do chat (Carregado via Bridge Async)
# chain.get_history_for_display() é async, precisamos rodar no event loop
try:
    messages = asyncio.run(chain.get_history_for_display())
except Exception as e:
    st.error(f"Erro ao carregar histórico: {e}")
    messages = []

for msg_id, user_msg, bot_msg, rating in messages:
    with st.chat_message("user"):
        st.write(user_msg)
    with st.chat_message("assistant"):
        st.write(bot_msg)
        display_feedback_buttons(chain, msg_id, existing_rating=rating)


# 4. Gerenciar nova entrada do usuário
prompt = st.chat_input("Faça sua pergunta sobre o Programa Quita Goiás...")

if prompt:
    # Exibe a pergunta do usuário
    with st.chat_message("user"):
        st.write(prompt)

    # Gera e exibe a resposta do assistente
    with st.chat_message("assistant"):
        with st.spinner("Buscando, re-rankeando e pensando..."):
            # Bridge Sync -> Async para gerar a resposta
            try:
                response_dict = asyncio.run(chain.generate_response(prompt))
                st.write(response_dict["answer"])

                # Exibe os botões de feedback para a *nova* mensagem
                if response_dict["message_id"]:
                    display_feedback_buttons(chain, response_dict["message_id"])
            except Exception as e:
                st.error(f"Ocorreu um erro ao gerar a resposta: {e}")

# Foco no input
set_focus()
