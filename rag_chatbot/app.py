# app.py
import streamlit as st
import uuid
from streamlit.components.v1 import html  # <-- 1. NOVO IMPORT
import os  # <<< --- IMPORT NECESSÁRIO ---

# Importa a nova classe RAGChain
from rag_chain import RAGChain


# --- 2. NOVA FUNÇÃO PARA FOCAR O INPUT ---
def set_focus():
    """
    Injeta JavaScript para focar automaticamente a caixa de chat_input.
    """
    # O seletor '[data-testid="stChatInput"] textarea' é a forma mais
    # confiável de encontrar a caixa de texto do st.chat_input.
    # Usamos setTimeout para dar tempo ao Streamlit de renderizar o elemento.
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
    # Injeta o script na página
    html(script, height=0)


# --- FIM DA NOVA FUNÇÃO ---

# --- NOVO: BOTÃO DE SAIR NA BARRA LATERAL ---
with st.sidebar:
    st.header("Controle da Aplicação")
    st.warning("Clicar em 'Sair' encerrará o servidor do Streamlit.")
    if st.button("Sair e Encerrar Aplicação"):
        print("Botão 'Sair' clicado. Encerrando o processo do servidor.")
        # Este comando força o processo Python a parar.
        # É a forma mais direta de "fechar" o servidor pela UI.
        os._exit(0)
# --- FIM DA NOVA SEÇÃO ---


st.title("Programa Quita Goiás")
st.caption("Processamento em Linguagem Natual - Turma 2 - Grupo 25")

# 1. Gerenciar o ID da Sessão (como na Solução 2)
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    print(f"Nova sessão criada: {st.session_state.session_id}")

# 2. Inicializar o RAGChain (passando o session_id)
# O Streamlit recria o objeto a cada interação,
# mas o estado é mantido no SQLite.
try:
    chain = RAGChain(st.session_state.session_id)
except FileNotFoundError as e:
    st.error(f"Erro: Banco de vetores não encontrado em '{e}'.")
    st.error("Execute 'python ingest.py' antes de iniciar o aplicativo.")
    st.stop()
except Exception as e:
    st.error(f"Erro ao inicializar a RAG Chain: {e}")
    st.stop()


# 3. Exibir o histórico do chat (Carregado do SQLite)
messages = chain.get_history_for_display()
for user_msg, bot_msg in messages:
    with st.chat_message("user"):
        st.write(user_msg)
    with st.chat_message("assistant"):
        st.write(bot_msg)

# 4. Gerenciar nova entrada do usuário
prompt = st.chat_input("Faça sua pergunta sobre os documentos...")
if prompt:
    # Exibe a pergunta do usuário
    with st.chat_message("user"):
        st.write(prompt)

    # Gera e exibe a resposta do assistente
    with st.chat_message("assistant"):
        with st.spinner("Buscando, re-rankeando e pensando..."):
            response = chain.generate_response(prompt)
            st.write(response)


# --- 3. CHAMADA DA FUNÇÃO DE FOCO ---
# Chamar a função de foco no final do script.
# Isso garante que ela execute em cada recarregamento da página
# (seja o carregamento inicial ou após enviar uma mensagem).
set_focus()
# --- FIM DA CHAMADA ---
