# app.py
import streamlit as st
import uuid

# Importa a nova classe RAGChain
from rag_chain import RAGChain

st.title("Chat RAG com Re-Ranking (Solução 1)")
st.caption("Usando ChromaDB, Google Gemini e SentenceTransformer Re-Ranker")

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
