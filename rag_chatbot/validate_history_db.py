# validate_history_db.py
import streamlit as st
import sqlite3
import os
import sys
import csv
from datetime import datetime

# Importar o arquivo de configuração do banco de dados
# para obter o caminho (DB_PATH)
import database as history_db


@st.cache_resource
def connect_to_db():
    """
    Conecta ao banco de dados SQLite do histórico e o armazena
    no cache do Streamlit.
    """
    st.write("Conectando ao banco de dados de histórico...")

    # Usa o DB_PATH do arquivo database.py
    db_path = history_db.DB_PATH

    if not os.path.exists(db_path):
        st.error(f"Erro: Arquivo do banco de dados não encontrado em '{db_path}'")
        st.error("Por favor, execute 'python database.py' primeiro para criá-lo.")
        st.stop()

    try:

        # Adiciona check_same_thread=False para permitir que
        # o cache do Streamlit funcione com SQLite.
        conn = sqlite3.connect(db_path, check_same_thread=False)

        st.sidebar.success(f"Conectado ao DB.")
        return conn
    except Exception as e:
        st.error(f"Ocorreu um erro ao conectar ao banco de dados: {e}")
        st.stop()


def run_list_sessions(conn):
    """Lógica da UI para o Modo 1: Listar Todas as Sessões"""
    st.subheader("Modo 1: Listar Todas as Sessões")
    st.info("Exibe um resumo de todas as conversas únicas, agrupadas por ID de Sessão.")

    if st.button("Carregar Resumo das Sessões"):
        with st.spinner("Consultando sessões..."):
            try:
                cursor = conn.cursor()
                # Query de list_sessions
                cursor.execute(
                    """
                    SELECT 
                        session_id, 
                        COUNT(*) as msg_count, 
                        MAX(response_end_time) as last_activity,
                        AVG(total_duration_sec) as avg_duration
                    FROM chat_history 
                    GROUP BY session_id
                    ORDER BY last_activity DESC
                """
                )
                rows = cursor.fetchall()

                if not rows:
                    st.warning("Nenhuma sessão encontrada no histórico.")
                    return

                st.success(f"Total de sessões únicas encontradas: {len(rows)}")

                # Prepara os dados para o DataFrame
                data = [
                    {
                        "ID DA SESSÃO": row[0],
                        "MSGS": row[1],
                        "ÚLTIMA ATIVIDADE": row[2],
                        "DURAÇÃO MÉDIA (s)": f"{row[3]:.2f}",
                    }
                    for row in rows
                ]
                st.dataframe(data, use_container_width=True)

            except Exception as e:
                st.error(f"Erro ao listar sessões: {e}")


def run_search_by_session(conn):
    """Lógica da UI para o Modo 2: Buscar por Sessão"""
    st.subheader("Modo 2: Buscar Histórico por Sessão")
    st.info("Digite um ID de Sessão (obtido no Modo 1) para ver uma conversa completa.")

    with st.form(key="session_search_form"):
        session_id = st.text_input(
            "ID da Sessão:", placeholder="ex: 172f1ed9-e649-4359-aa24-f01dadf0ce4e"
        )
        submit_button = st.form_submit_button(label="Buscar")

    if submit_button and session_id:
        st.write(f"Buscando pela Sessão: {session_id}")
        with st.spinner("Consultando histórico da sessão..."):
            try:
                cursor = conn.cursor()
                # Query de search_by_session
                cursor.execute(
                    """
                    SELECT id, user_message, bot_response, 
                           user_chars, bot_chars, user_tokens, bot_tokens,
                           request_start_time, retrieval_duration_sec, 
                           generation_duration_sec, total_duration_sec
                    FROM chat_history 
                    WHERE session_id = ? 
                    ORDER BY request_start_time ASC
                """,
                    (session_id.strip(),),
                )
                rows = cursor.fetchall()

                if not rows:
                    st.warning(
                        f"Nenhum histórico encontrado para a sessão: '{session_id}'"
                    )
                    return

                st.success(
                    f"Total de mensagens encontradas para esta sessão: {len(rows)}"
                )

                # Exibe as mensagens (lógica de read_db_history.py)
                for row in rows:
                    (
                        id,
                        user_msg,
                        bot_msg,
                        u_chars,
                        b_chars,
                        u_tokens,
                        b_tokens,
                        start,
                        retr_dur,
                        gen_dur,
                        total_dur,
                    ) = row
                    with st.container(border=True):
                        st.markdown(f"**ID da Mensagem: {id}** | Início: {start}")
                        st.caption(
                            f"Duração (s): Total={total_dur:<.2f} (Recup: {retr_dur:<.2f}s, Geração: {gen_dur:<.2f}s)"
                        )
                        st.text(
                            f"USUÁRIO (Chars: {u_chars}, Tokens: {u_tokens}): {user_msg}"
                        )
                        st.text(
                            f"ASSIST. (Chars: {b_chars}, Tokens: {b_tokens}): {bot_msg}"
                        )

            except Exception as e:
                st.error(f"Erro ao buscar pela sessão: {e}")


def run_list_all(conn):
    """Lógica da UI para o Modo 3: Ver Histórico Completo"""
    st.subheader("Modo 3: Ver Histórico Completo")
    st.warning(
        "Atenção: Isso pode carregar um grande volume de dados se o banco for grande."
    )

    if st.button("Carregar TODO o histórico"):
        with st.spinner("Consultando todo o histórico..."):
            try:
                cursor = conn.cursor()
                # Query de read_all_history
                cursor.execute(
                    """
                    SELECT id, session_id, user_message, bot_response, 
                           user_chars, bot_chars, user_tokens, bot_tokens,
                           request_start_time, retrieval_duration_sec, 
                           generation_duration_sec, total_duration_sec
                    FROM chat_history 
                    ORDER BY request_start_time ASC
                """
                )
                rows = cursor.fetchall()

                if not rows:
                    st.warning("O banco de dados de histórico está vazio.")
                    return

                st.success(f"Total de mensagens encontradas: {len(rows)}")

                # Exibe as mensagens (lógica de read_db_history.py)
                for row in rows:
                    (
                        id,
                        session_id,
                        user_msg,
                        bot_msg,
                        u_chars,
                        b_chars,
                        u_tokens,
                        b_tokens,
                        start,
                        retr_dur,
                        gen_dur,
                        total_dur,
                    ) = row
                    with st.container(border=True):
                        st.markdown(
                            f"**ID: {id}** | Sessão: {session_id} | Início: {start}"
                        )
                        st.caption(
                            f"Duração (s): Total={total_dur:<.2f} (Recup: {retr_dur:<.2f}s, Geração: {gen_dur:<.2f}s)"
                        )
                        st.text(
                            f"USUÁRIO (Chars: {u_chars}, Tokens: {u_tokens}): {user_msg}"
                        )
                        st.text(
                            f"ASSIST. (Chars: {b_chars}, Tokens: {b_tokens}): {bot_msg}"
                        )

            except Exception as e:
                st.error(f"Erro ao ler o histórico: {e}")


def run_list_feedback(conn):
    """Lógica da UI para o Modo 4: Ver Avaliações (Feedback) - NOVO"""
    st.subheader("Modo 4: Ver Avaliações (Feedback)")
    st.info("Exibe todas as avaliações (like/dislike) dadas pelos usuários.")

    if st.button("Carregar Todas as Avaliações"):
        with st.spinner("Consultando avaliações..."):
            try:
                cursor = conn.cursor()
                #
                # Query para buscar feedbacks com o contexto da conversa
                cursor.execute(
                    """
                    SELECT 
                        f.id as feedback_id,
                        f.rating,
                        f.timestamp as feedback_time,
                        f.comment,
                        h.id as message_id,
                        h.session_id,
                        h.user_message,
                        h.bot_response
                    FROM feedback f
                    JOIN chat_history h ON f.message_id = h.id
                    ORDER BY f.timestamp DESC
                """
                )
                rows = cursor.fetchall()

                if not rows:
                    st.warning(
                        "Nenhuma avaliação (feedback) encontrada no banco de dados."
                    )
                    return

                st.success(f"Total de avaliações encontradas: {len(rows)}")

                # Exibe os feedbacks
                for row in rows:
                    (
                        fb_id,
                        rating,
                        fb_time,
                        comment,
                        msg_id,
                        session_id,
                        user_msg,
                        bot_msg,
                    ) = row

                    icon = "👍" if rating == "like" else "👎"

                    with st.container(border=True):
                        st.markdown(
                            f"**Avaliação: {icon} (ID: {fb_id})** | Data: {fb_time}"
                        )
                        st.caption(f"Sessão: {session_id} | ID da Mensagem: {msg_id}")
                        if comment:
                            st.write(f"Comentário: {comment}")

                        st.text(f"USUÁRIO: {user_msg}")
                        st.text(f"ASSISTENTE: {bot_msg}")

            except Exception as e:
                st.error(f"Erro ao ler o histórico de feedback: {e}")


def run_export_csv(conn):
    """Lógica da UI para o Modo 5: Exportar Histórico para CSV"""
    st.subheader("Modo 5: Exportar Histórico para CSV")
    st.info("O arquivo será salvo na pasta raiz do projeto.")

    if st.button("Gerar Arquivo 'historico_chat_exportado.csv'"):
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        output_filename = "historico_chat_exportado.csv"
        output_path = os.path.join(SCRIPT_DIR, output_filename)

        with st.spinner("Exportando histórico para CSV..."):
            try:
                cursor = conn.cursor()
                # Query de export_history_to_csv
                cursor.execute(
                    "SELECT * FROM chat_history ORDER BY request_start_time ASC"
                )

                rows = cursor.fetchall()
                if not rows:
                    st.error("Nada para exportar, o histórico está vazio.")
                    return

                headers = [description[0] for description in cursor.description]

                with open(output_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    writer.writerows(rows)

                st.success(f"\nSucesso! {len(rows)} mensagens exportadas para:")
                st.code(output_path, language="bash")

            except Exception as e:
                st.error(f"\nErro ao salvar o arquivo CSV: {e}")


def run_shutdown():
    """Lógica da UI para o Modo 6: Encerrar"""
    st.subheader("Modo 6: Encerrar Servidor")
    st.warning("Clicar neste botão encerrará este servidor Streamlit.")

    if st.button("Encerrar Aplicação"):
        st.success("Encerrando servidor...")
        print("Comando de encerramento recebido da UI.")
        os._exit(0)  # Força a parada do processo Python


# --- Ponto de Entrada Principal da Aplicação ---
def main():
    st.set_page_config(page_title="Auditoria do Histórico", layout="wide")
    st.title("Ferramenta de Auditoria do Histórico de Chat (SQLite)")
    st.caption("Esta interface consulta o banco de dados 'chat_solution.db'.")

    # Inicializa a conexão com o DB (usando o cache)
    conn = connect_to_db()

    # --- Barra Lateral de Navegação ---
    st.sidebar.title("Opções de Auditoria")
    opcoes = [
        "1. Listar Todas as Sessões",
        "2. Buscar por Sessão",
        "3. Ver Histórico Completo",
        "4. Ver Avaliações (Feedback)",
        "5. Exportar Histórico para CSV",
        "6. Encerrar Servidor",
    ]
    modo = st.sidebar.radio(
        "Selecione uma operação:", opcoes, label_visibility="collapsed"
    )

    # --- Exibe a página correta baseada na seleção ---
    if modo == opcoes[0]:
        run_list_sessions(conn)

    elif modo == opcoes[1]:
        run_search_by_session(conn)

    elif modo == opcoes[2]:
        run_list_all(conn)

    elif modo == opcoes[3]:
        run_list_feedback(conn)

    elif modo == opcoes[4]:
        run_export_csv(conn)

    elif modo == opcoes[5]:
        run_shutdown()


if __name__ == "__main__":
    main()
