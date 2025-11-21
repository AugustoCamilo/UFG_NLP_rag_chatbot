# validate_history_db.py
"""
Módulo de Dashboard de Auditoria do Histórico de Produção.

Atualizado para:
1. Usar Callbacks no botão de navegação (Correção do bug de reset).
2. Usar settings.py.
3. Exportar CSV com timestamp.
4. Usar SQLModel.
"""

import streamlit as st
import pandas as pd
import os
from datetime import datetime
from sqlmodel import Session, create_engine, select, func, desc

# --- Imports do Projeto ---
from settings import settings
from ui_utils import add_print_to_pdf_button
from database import ChatHistory, Feedback

# --- Configuração do Engine Síncrono ---
engine = create_engine(settings.SYNC_DATABASE_URL)


def get_session_sync():
    """Retorna uma sessão síncrona."""
    return Session(engine)


# --- CALLBACK DE NAVEGAÇÃO (A CORREÇÃO MÁGICA) ---
def ir_para_busca(session_id):
    """
    Função executada ANTES do rerun, garantindo que o estado
    esteja atualizado quando a interface for redesenhada.
    """
    st.session_state["target_session_id"] = session_id
    # O valor aqui DEVE ser idêntico ao texto da opção no menu
    st.session_state["sb_menu"] = "2. Buscar Sessão"


def run_list_sessions():
    """Modo 1: Listar Todas as Sessões"""
    st.subheader("Modo 1: Listar Todas as Sessões")

    if st.button("Carregar Resumo das Sessões"):
        with st.spinner("Consultando sessões via SQLModel..."):
            with get_session_sync() as session:
                statement = (
                    select(
                        ChatHistory.session_id,
                        func.count(ChatHistory.id).label("msg_count"),
                        func.max(ChatHistory.response_end_time).label("last_activity"),
                        func.avg(ChatHistory.total_duration_sec).label("avg_duration"),
                    )
                    .group_by(ChatHistory.session_id)
                    .order_by(desc("last_activity"))
                )
                results = session.exec(statement).all()

                if not results:
                    st.warning("Nenhuma sessão encontrada.")
                    return

                st.success(f"Total de sessões encontradas: {len(results)}")
                st.markdown("---")

                # --- Cabeçalho ---
                c1, c2, c3, c4, c5 = st.columns([4, 1, 2, 1, 1.5])
                c1.markdown("**ID da Sessão**")
                c2.markdown("**Msgs**")
                c3.markdown("**Última Atividade**")
                c4.markdown("**Tempo**")
                c5.markdown("**Ação**")
                st.divider()

                # --- Loop ---
                for row in results:
                    c1, c2, c3, c4, c5 = st.columns([4, 1, 2, 1, 1.5])

                    # Coluna 1: ID com botão de cópia nativo
                    c1.code(row.session_id, language="text")

                    c2.write(f"{row.msg_count}")
                    c3.write(
                        f"{row.last_activity.strftime('%d/%m %H:%M') if row.last_activity else 'N/A'}"
                    )
                    c4.write(f"{row.avg_duration:.2f}s")

                    # Coluna 5: Botão com CALLBACK
                    # Note o uso de on_click e args. Não usamos 'if button:'
                    c5.button(
                        "📂 Abrir",
                        key=f"btn_open_{row.session_id}",
                        on_click=ir_para_busca,
                        args=(row.session_id,),
                    )

                    st.markdown("---")


def run_search_by_session():
    """Modo 2: Buscar por Sessão"""
    st.subheader("Modo 2: Buscar Histórico por Sessão")

    # Verifica se veio um ID do callback
    default_id = st.session_state.get("target_session_id", "")

    with st.form(key="session_search_form"):
        # O value=default_id preenche automaticamente
        session_id = st.text_input("ID da Sessão:", value=default_id)
        submit_button = st.form_submit_button(label="Buscar")

    # Executa a busca se clicou no botão OU se veio redirecionado (tem default_id)
    # A verificação (submit_button or default_id) garante que rode na primeira carga
    if (submit_button or default_id) and session_id:

        # Opcional: Limpar o target para evitar comportamento "pegajoso" futuro
        # mas mantendo por enquanto para permitir refresh da página

        with st.spinner("Buscando mensagens..."):
            with get_session_sync() as session:
                statement = (
                    select(ChatHistory)
                    .where(ChatHistory.session_id == session_id.strip())
                    .order_by(ChatHistory.request_start_time)
                )
                messages = session.exec(statement).all()

                if not messages:
                    st.warning("Sessão não encontrada.")
                    return

                st.success(f"Encontradas {len(messages)} mensagens.")
                for msg in messages:
                    with st.container(border=True):
                        st.markdown(f"**ID: {msg.id}** | {msg.request_start_time}")
                        st.text(f"USER: {msg.user_message}")
                        st.text(f"BOT:  {msg.bot_response}")
                        st.caption(f"Tokens: U={msg.user_tokens} / B={msg.bot_tokens}")


def run_list_feedback():
    """Modo 3: Ver Avaliações"""
    st.subheader("Modo 3: Ver Avaliações (Feedback)")

    if st.button("Carregar Feedbacks"):
        with get_session_sync() as session:
            statement = (
                select(Feedback, ChatHistory)
                .join(ChatHistory, Feedback.message_id == ChatHistory.id)
                .order_by(desc(Feedback.timestamp))
            )
            results = session.exec(statement).all()

            if not results:
                st.warning("Nenhum feedback encontrado.")
                return

            for feedback, history in results:
                icon = "👍" if feedback.rating == "like" else "👎"
                with st.container(border=True):
                    st.markdown(
                        f"**{icon} {feedback.rating.upper()}** | {feedback.timestamp}"
                    )
                    if feedback.comment:
                        st.info(f"Comentário: {feedback.comment}")
                    st.text(f"Q: {history.user_message}")
                    st.text(f"A: {history.bot_response}")


def run_export_csv():
    """Modo 4: Exportar para CSV"""
    st.subheader("Modo 4: Exportar Histórico Completo")

    if st.button("Gerar Arquivo CSV"):
        file_timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        output_filename = f"historico_chat_{file_timestamp}.csv"

        with st.spinner("Exportando..."):
            try:
                statement = select(ChatHistory).order_by(ChatHistory.request_start_time)
                df = pd.read_sql(statement, engine)

                if df.empty:
                    st.warning("Histórico vazio.")
                    return

                df.to_csv(output_filename, index=False)
                st.success(f"Sucesso! Exportado para: {output_filename}")
                st.code(output_filename, language="text")

            except Exception as e:
                st.error(f"Erro ao exportar CSV: {e}")


def run_shutdown():
    """Modo 5: Sair"""
    st.subheader("Modo 5: Sair")
    st.warning("Clicar neste botão encerrará este servidor Streamlit.")
    if st.button("Encerrar Aplicação"):
        st.success("Encerrando servidor...")
        print("Comando de encerramento recebido da UI.")
        os._exit(0)


def main():
    st.set_page_config(page_title="Auditoria Histórico", layout="wide")
    st.title("Auditoria do Histórico (SQLModel)")

    st.sidebar.title("Menu")
    add_print_to_pdf_button()
    st.sidebar.markdown("---")

    # As chaves do dicionário DEVEM ser idênticas à string usada em ir_para_busca
    options = {
        "1. Listar Sessões": run_list_sessions,
        "2. Buscar Sessão": run_search_by_session,
        "3. Ver Feedbacks": run_list_feedback,
        "4. Exportar CSV": run_export_csv,
        "5. Sair": run_shutdown,
    }

    # Se não houver menu no estado, define o padrão
    if "sb_menu" not in st.session_state:
        st.session_state["sb_menu"] = list(options.keys())[0]

    # O widget radio agora "escuta" o estado (key="sb_menu") e atualiza ele também
    choice = st.sidebar.radio("Opções", list(options.keys()), key="sb_menu")

    options[choice]()


if __name__ == "__main__":
    main()
