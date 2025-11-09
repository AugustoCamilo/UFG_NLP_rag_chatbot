# validate_history_db.py
"""
Módulo de Dashboard de Auditoria do Histórico de Produção.

Esta aplicação Streamlit é uma ferramenta de "Business Intelligence" (BI)
focada em analisar o uso real do chatbot (o frontend `app.py`).

Ele se conecta ao `chat_solution.db` e foca na leitura das
tabelas `chat_history` e `feedback` para responder perguntas como:
- "Quantas pessoas usaram o bot?"
- "Qual foi a conversa completa de um usuário específico?"
- "Quais respostas receberam feedback negativo?"

---
### Funcionalidades Principais (Modos)
---

A aplicação é dividida em seis modos principais, selecionáveis
na barra lateral:

1.  **Listar Todas as Sessões:**
    * Executa `run_list_sessions`.
    * Agrupa a tabela `chat_history` por `session_id`.
    * Fornece um resumo de alto nível de quantas conversas únicas
        aconteceram, quantas mensagens elas tiveram e qual foi a
        duração média.

2.  **Buscar por Sessão:**
    * Executa `run_search_by_session`.
    * Permite que o administrador insira um `session_id` (obtido no Modo 1)
        para ver a transcrição completa daquela conversa específica.
    * Exibe métricas de performance (tokens, duração) para cada
        mensagem na sessão.

3.  **Ver Histórico Completo:**
    * Executa `run_list_all`.
    * Carrega e exibe *todas as mensagens de todas as sessões* em
        ordem cronológica. Útil para uma visão geral ou
        para depuração de baixo nível.

4.  **Ver Avaliações (Feedback):**
    * Executa `run_list_feedback`.
    * Faz um `JOIN` entre as tabelas `feedback` e `chat_history`.
    * Exibe todas as avaliações (👍/👎) junto com a pergunta
        e a resposta que receberam a avaliação, permitindo uma
        análise qualitativa imediata de respostas problemáticas.

5.  **Exportar Histórico para CSV:**
    * Executa `run_export_csv`.
    * Exporta a tabela `chat_history` inteira para um arquivo CSV
        (`historico_chat_exportado.csv`) para análise
        externa em ferramentas como Excel ou Power BI.

6.  **Encerrar Servidor:**
    * Uma função de conveniência (`run_shutdown`) que chama
        `os._exit(0)` para parar o processo do Streamlit.
"""


import streamlit as st
import sqlite3
import os
import sys
import csv
from datetime import datetime
from streamlit.components.v1 import html

# Importar o arquivo de configuração do banco de dados
# para obter o caminho (DB_PATH)
import database as history_db


def add_print_to_pdf_button():
    """
    Adiciona CSS para formatar a página para impressão e um botão
    discreto que aciona o diálogo de impressão (window.print()).
    """

    # 1. CSS (O "Canhão" para forçar tudo preto na impressão)
    print_css = """
    <style>
    @media print {
        /* Esconde elementos da UI */
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stHeader"] { display: none; }
        .no-print { display: none !important; }
        
        /* Otimiza o layout */
        [data-testid="stAppViewContainer"] { padding-top: 0; }
        
        /* 1. Força o fundo para branco */
        body, [data-testid="stAppViewContainer"] {
            background: #ffffff !important;
        }

        /* 2. O "Canhão": Força TODO o texto (títulos, etc.) 
           a ser PRETO. */
        * {
            color: #000000 !important;
        }
    }
    </style>
    """
    st.markdown(print_css, unsafe_allow_html=True)

    # 2. O Botão (CSS inalterado)
    button_style = """
        background-color: transparent;
        border: none;
        color: #0068C9; /* Cor azul (padrão de link) */
        cursor: pointer;
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 0.95rem; /* Tamanho de fonte padrão */
        padding: 0.25rem 0rem; /* Padding vertical leve */
        margin: 0.5rem 0;
        text-align: left; /* Alinha à esquerda */
        opacity: 0.8; /* Ligeiramente transparente */
        transition: opacity 0.2s;
    """

    # 3. O HTML do Botão (inalterado)
    button_html = f"""
    <button
        onclick="window.parent.print()"
        class="no-print"
        style="{button_style}"
        onmouseover="this.style.opacity=1"
        onmouseout="this.style.opacity=0.8"
        title="Imprimir esta página (Salvar como PDF)"
    >
        🖨️ Imprimir página
    </button>
    """

    # 4. A Chamada (inalterada)
    html(button_html, height=50)


# --- INÍCIO DA ALTERAÇÃO ---
# REMOVIDO: @st.cache_resource
# Não podemos cachear a conexão, pois ela fica "stale" (vencida)
# e não vê as escritas feitas pelo app.py (outro processo).
def connect_to_db():
    """
    Conecta ao banco de dados SQLite do histórico.
    Esta função agora é chamada por cada modo, garantindo uma conexão nova.
    """
    db_path = history_db.DB_PATH

    if not os.path.exists(db_path):
        st.error(f"Erro: Arquivo do banco de dados não encontrado em '{db_path}'")
        st.error("Por favor, execute 'python database.py' primeiro para criá-lo.")
        st.stop()
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        return conn
    except Exception as e:
        st.error(f"Ocorreu um erro ao conectar ao banco de dados: {e}")
        st.stop()


def run_list_sessions():
    """Modo 1: Listar Todas as Sessões"""
    st.subheader("Modo 1: Listar Todas as Sessões")
    st.info("Exibe um resumo de todas as conversas únicas, agrupadas por ID de Sessão.")

    if st.button("Carregar Resumo das Sessões"):
        with st.spinner("Consultando sessões..."):

            # --- Bloco de conexão/fechamento ---
            conn = None
            try:
                conn = connect_to_db()  # Abre uma nova conexão
                cursor = conn.cursor()
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
                # ... (resto da lógica de exibição do dataframe) ...
                if not rows:
                    st.warning("Nenhuma sessão encontrada no histórico.")
                    return

                st.success(f"Total de sessões únicas encontradas: {len(rows)}")
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
            finally:
                if conn:
                    conn.close()  # Fecha a conexão
            # --- Fim do bloco ---


def run_search_by_session():
    """Modo 2: Buscar por Sessão"""
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

            # --- Bloco de conexão/fechamento ---
            conn = None
            try:
                conn = connect_to_db()  # Abre uma nova conexão
                cursor = conn.cursor()
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
                # ... (resto da lógica de exibição) ...
                if not rows:
                    st.warning(
                        f"Nenhum histórico encontrado para a sessão: '{session_id}'"
                    )
                    return
                st.success(
                    f"Total de mensagens encontradas para esta sessão: {len(rows)}"
                )
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
            finally:
                if conn:
                    conn.close()  # Fecha a conexão
            # --- Fim do bloco ---


def run_list_all():  # <-- 1. REMOVIDO 'conn' DAQUI
    """Modo 3: Ver Histórico Completo"""
    st.subheader("Modo 3: Ver Histórico Completo")  #
    st.warning(
        "Atenção: Isso pode carregar um grande volume de dados se o banco for grande."
    )  #

    if st.button("Carregar TODO o histórico"):  #
        with st.spinner("Consultando todo o histórico..."):  #

            # --- 2. ADICIONADO O BLOCO DE CONEXÃO ---
            conn = None
            try:
                conn = connect_to_db()  # Abre uma nova conexão
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, session_id, user_message, bot_response, 
                           user_chars, bot_chars, user_tokens, bot_tokens,
                           request_start_time, retrieval_duration_sec, 
                           generation_duration_sec, total_duration_sec
                    FROM chat_history 
                    ORDER BY request_start_time ASC
                """
                )  #
                rows = cursor.fetchall()  #

                if not rows:  #
                    st.warning("O banco de dados de histórico está vazio.")  #
                    return

                st.success(f"Total de mensagens encontradas: {len(rows)}")  #
                for row in rows:  #
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
                    ) = row  #
                    with st.container(border=True):  #
                        st.markdown(
                            f"**ID: {id}** | Sessão: {session_id} | Início: {start}"
                        )  #
                        st.caption(
                            f"Duração (s): Total={total_dur:<.2f} (Recup: {retr_dur:<.2f}s, Geração: {gen_dur:<.2f}s)"
                        )  #
                        st.text(
                            f"USUÁRIO (Chars: {u_chars}, Tokens: {u_tokens}): {user_msg}"
                        )  #
                        st.text(
                            f"ASSIST. (Chars: {b_chars}, Tokens: {b_tokens}): {bot_msg}"
                        )  #

            except Exception as e:
                st.error(f"Erro ao ler o histórico: {e}")  #
            finally:
                if conn:
                    conn.close()  # Fecha a conexão


def run_list_feedback():
    """Modo 4: Ver Avaliações (Feedback)"""
    st.subheader("Modo 4: Ver Avaliações (Feedback)")
    st.info("Exibe todas as avaliações (like/dislike) dadas pelos usuários.")

    if st.button("Carregar Todas as Avaliações"):
        with st.spinner("Consultando avaliações..."):

            # --- Bloco de conexão/fechamento ---
            conn = None
            try:
                conn = connect_to_db()  # Abre uma nova conexão
                cursor = conn.cursor()
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
            finally:
                if conn:
                    conn.close()  # Fecha a conexão
            # --- Fim do bloco ---


def run_export_csv():
    """Modo 5: Exportar Histórico para CSV"""
    st.subheader("Modo 5: Exportar Histórico para CSV")
    st.info("O arquivo será salvo na pasta raiz do projeto.")

    if st.button("Gerar Arquivo 'historico_chat_exportado.csv'"):
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        output_filename = "historico_chat_exportado.csv"
        output_path = os.path.join(SCRIPT_DIR, output_filename)

        with st.spinner("Exportando histórico para CSV..."):

            # --- Bloco de conexão/fechamento ---
            conn = None
            try:
                conn = connect_to_db()  # Abre uma nova conexão
                cursor = conn.cursor()
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
            finally:
                if conn:
                    conn.close()  # Fecha a conexão
            # --- Fim do bloco ---


def run_shutdown():
    """Modo 6: Encerrar"""
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

    # --- INÍCIO DA ALTERAÇÃO ---
    # Removida a chamada 'conn = connect_to_db()' daqui.
    # Cada função 'run_...' agora gerencia sua própria conexão.
    # --- FIM DA ALTERAÇÃO ---

    # --- Barra Lateral de Navegação ---
    st.sidebar.title("Opções de Auditoria")

    st.sidebar.markdown("---")
    add_print_to_pdf_button()
    st.sidebar.markdown("---")

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
        run_list_sessions()  # Chamada sem 'conn'

    elif modo == opcoes[1]:
        run_search_by_session()  # Chamada sem 'conn'

    elif modo == opcoes[2]:
        run_list_all()  # Chamada sem 'conn' (Ops, esqueci de remover o arg)

    elif modo == opcoes[3]:
        run_list_feedback()  # Chamada sem 'conn'

    elif modo == opcoes[4]:
        run_export_csv()  # Chamada sem 'conn'

    elif modo == opcoes[5]:
        run_shutdown()


if __name__ == "__main__":
    main()
