# validate_history_db.py
"""
Módulo de Dashboard de Auditoria do Histórico de Produção.

Atualizado para:
1. Usar Callbacks no botão de navegação.
2. Usar settings.py.
3. Exportar CSV com timestamp e identificação de origem.
4. Usar SQLModel.
5. Resumo Estatístico agrupado por Origem (Real vs Sintético).
6. Importação e Exportação de XML (Backup completo).
"""

import streamlit as st
import pandas as pd
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
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


def _safe_get_text(element, tag, default=None):
    """Helper para ler XML de forma segura."""
    found = element.find(tag)
    if found is not None and found.text is not None:
        return found.text
    return default


# --- CALLBACK DE NAVEGAÇÃO ---
def ir_para_busca(session_id):
    """
    Função executada ANTES do rerun, garantindo que o estado
    esteja atualizado quando a interface for redesenhada.
    """
    st.session_state["target_session_id"] = session_id
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
                        # Pegamos o max(is_synthetic) para saber se a sessão teve flag de teste
                        func.max(ChatHistory.is_synthetic).label("is_synthetic_flag"),
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

                # Cabeçalho da Tabela
                c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 2, 1.5])
                c1.markdown("**ID da Sessão**")
                c2.markdown("**Origem**")
                c3.markdown("**Msgs**")
                c4.markdown("**Última Atividade**")
                c5.markdown("**Ação**")
                st.divider()

                for row in results:
                    c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 2, 1.5])

                    origin_icon = "🧪" if row.is_synthetic_flag else "👤"

                    c1.code(row.session_id, language="text")
                    c2.write(origin_icon)
                    c3.write(f"{row.msg_count}")
                    c4.write(
                        f"{row.last_activity.strftime('%d/%m %H:%M') if row.last_activity else 'N/A'}"
                    )
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

    default_id = st.session_state.get("target_session_id", "")

    with st.form(key="session_search_form"):
        session_id = st.text_input("ID da Sessão:", value=default_id)
        submit_button = st.form_submit_button(label="Buscar")

    if (submit_button or default_id) and session_id:
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
                    origin_lbl = "🧪 Teste" if msg.is_synthetic else "👤 Real"
                    with st.container(border=True):
                        col_top, col_origin = st.columns([5, 1])
                        col_top.markdown(f"**ID: {msg.id}** | {msg.request_start_time}")
                        col_origin.caption(f"Origem: {origin_lbl}")

                        st.text(f"USER: {msg.user_message}")
                        st.text(f"BOT:  {msg.bot_response}")
                        st.caption(f"Tokens: U={msg.user_tokens} / B={msg.bot_tokens}")


def run_list_feedback():
    """Modo 3: Ver Avaliações Detalhadas"""
    st.subheader("Modo 3: Ver Avaliações (Detalhado)")

    if st.button("Carregar Lista de Feedbacks"):
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

                # Definição do Label de Origem
                if history.is_synthetic:
                    origin_label = "🧪 Teste Sintético"
                    origin_color = "orange"
                else:
                    origin_label = "👤 Usuário Real"
                    origin_color = "blue"

                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(
                        f"**{icon} {feedback.rating.upper()}** | {feedback.timestamp}"
                    )
                    c2.markdown(f":{origin_color}[**{origin_label}**]")

                    if feedback.comment:
                        st.info(f"Comentário: {feedback.comment}")
                    st.text(f"Q: {history.user_message}")
                    st.text(f"A: {history.bot_response}")


def run_feedback_summary():
    """Modo 4: Resumo dos Feedbacks"""
    st.subheader("Modo 4: Resumo dos Feedbacks (Estatísticas por Origem)")
    st.info("Estatísticas consolidadas de satisfação, separadas por tipo de interação.")

    if st.button("Calcular Estatísticas"):
        with get_session_sync() as session:

            # Vamos iterar pelos dois tipos de origem: Real (False) e Sintético (True)
            origins_to_check = [
                {"label": "👤 Usuário Real", "is_synthetic": False},
                {"label": "🧪 Teste Sintético", "is_synthetic": True},
            ]

            consolidated_data = []

            for origin in origins_to_check:
                is_synth = origin["is_synthetic"]
                label_origin = origin["label"]

                # 1. Total de Interações desta origem
                total_msgs = session.exec(
                    select(func.count(ChatHistory.id)).where(
                        ChatHistory.is_synthetic == is_synth
                    )
                ).one()

                if total_msgs == 0:
                    continue

                # 2. Likes (Join necessário para filtrar por origem no ChatHistory)
                likes = session.exec(
                    select(func.count(Feedback.id))
                    .join(ChatHistory, Feedback.message_id == ChatHistory.id)
                    .where(Feedback.rating == "like")
                    .where(ChatHistory.is_synthetic == is_synth)
                ).one()

                # 3. Dislikes
                dislikes = session.exec(
                    select(func.count(Feedback.id))
                    .join(ChatHistory, Feedback.message_id == ChatHistory.id)
                    .where(Feedback.rating == "dislike")
                    .where(ChatHistory.is_synthetic == is_synth)
                ).one()

                # 4. Em Branco
                total_feedbacks = likes + dislikes
                blanks = total_msgs - total_feedbacks
                if blanks < 0:
                    blanks = 0

                # 5. Cálculos
                pct_likes = (likes / total_msgs) * 100
                pct_dislikes = (dislikes / total_msgs) * 100
                pct_blanks = (blanks / total_msgs) * 100

                # Adicionar linhas ao dataset
                consolidated_data.append(
                    {
                        "Origem": label_origin,
                        "Métrica": "👍 Likes",
                        "Total": likes,
                        "Porcentagem": f"{pct_likes:.2f}%",
                    }
                )
                consolidated_data.append(
                    {
                        "Origem": label_origin,
                        "Métrica": "👎 Dislikes",
                        "Total": dislikes,
                        "Porcentagem": f"{pct_dislikes:.2f}%",
                    }
                )
                consolidated_data.append(
                    {
                        "Origem": label_origin,
                        "Métrica": "⬜ Em Branco",
                        "Total": blanks,
                        "Porcentagem": f"{pct_blanks:.2f}%",
                    }
                )
                consolidated_data.append(
                    {
                        "Origem": label_origin,
                        "Métrica": "TOTAL",
                        "Total": total_msgs,
                        "Porcentagem": "100%",
                    }
                )

            if not consolidated_data:
                st.warning("Nenhum dado encontrado para gerar estatísticas.")
                return

            df = pd.DataFrame(consolidated_data)

            # Reordenar colunas
            df = df[["Origem", "Métrica", "Total", "Porcentagem"]]

            st.table(df)


def run_export_csv():
    """Modo 5: Exportar para CSV"""
    st.subheader("Modo 5: Exportar Histórico Completo (CSV)")

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

                # Melhoria: Adicionar coluna descritiva para a origem
                df["origem_desc"] = df["is_synthetic"].apply(
                    lambda x: "Teste Sintético" if x else "Usuário Real"
                )

                # Reordenar para colocar a origem logo no início
                cols = list(df.columns)
                cols.insert(2, cols.pop(cols.index("origem_desc")))
                df = df[cols]

                df.to_csv(output_filename, index=False)
                st.success(f"Sucesso! Exportado para: {output_filename}")
                st.code(output_filename, language="text")

            except Exception as e:
                st.error(f"Erro ao exportar CSV: {e}")


def run_export_xml():
    """Modo 6: Exportar XML"""
    st.subheader("Modo 6: Exportar Histórico (XML)")
    st.info("Gera um backup completo em XML, incluindo feedbacks aninhados.")

    if st.button("Gerar Arquivo XML"):
        with get_session_sync() as session:
            # Busca todas as mensagens
            history_records = session.exec(
                select(ChatHistory).order_by(ChatHistory.request_start_time)
            ).all()

            if not history_records:
                st.warning("Histórico vazio.")
                return

            root = ET.Element("chat_database_export")
            timestamp_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            root.insert(
                0,
                ET.Comment(
                    f" Exportado em: {timestamp_now} | Total msgs: {len(history_records)} "
                ),
            )

            for record in history_records:
                msg_el = ET.SubElement(root, "chat_message")

                # Adiciona campos do ChatHistory
                for k, v in record.model_dump().items():
                    if v is not None:
                        ET.SubElement(msg_el, k).text = str(v)

                # Verifica e adiciona Feedback se existir
                feedback = session.exec(
                    select(Feedback).where(Feedback.message_id == record.id)
                ).first()
                if feedback:
                    fb_el = ET.SubElement(msg_el, "feedback")
                    for k, v in feedback.model_dump().items():
                        if (
                            k != "message_id" and v is not None
                        ):  # message_id é redundante aqui
                            ET.SubElement(fb_el, k).text = str(v)

            # Pretty Print
            xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
            file_timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            filename = f"historico_backup_{file_timestamp}.xml"

            with open(filename, "w", encoding="utf-8") as f:
                f.write(xml_str)

            st.success("Exportação XML concluída!")
            st.code(filename, language="text")


def run_import_xml():
    """Modo 7: Importar XML"""
    st.subheader("Modo 7: Importar Histórico (XML)")
    st.info(
        "Importa mensagens e feedbacks. Evita duplicatas baseando-se no ID da Sessão + Timestamp."
    )

    uploaded_file = st.file_uploader(
        "Selecione arquivo XML (historico_backup_*.xml)", type=["xml"]
    )

    if uploaded_file and st.button("Iniciar Importação"):
        imported_count = 0
        skipped_count = 0

        try:
            tree = ET.parse(uploaded_file)
            root = tree.getroot()

            messages_nodes = root.findall("chat_message")

            with get_session_sync() as session:
                for msg_node in messages_nodes:
                    # 1. Identificação para evitar duplicatas
                    sess_id = _safe_get_text(msg_node, "session_id")
                    ts_str = _safe_get_text(msg_node, "request_start_time")

                    if not sess_id or not ts_str:
                        continue

                    try:
                        ts_dt = datetime.fromisoformat(ts_str)
                    except ValueError:
                        try:
                            ts_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
                        except:
                            ts_dt = datetime.now()  # Fallback

                    # Verifica duplicidade
                    existing = session.exec(
                        select(ChatHistory)
                        .where(ChatHistory.session_id == sess_id)
                        .where(ChatHistory.request_start_time == ts_dt)
                    ).first()

                    if existing:
                        skipped_count += 1
                        continue

                    # 2. Criar Objeto ChatHistory
                    # Precisamos converter strings booleanas corretamente
                    is_synth_str = _safe_get_text(msg_node, "is_synthetic", "False")
                    is_synth_val = is_synth_str == "True"

                    chat_entry = ChatHistory(
                        session_id=sess_id,
                        user_message=_safe_get_text(msg_node, "user_message", ""),
                        bot_response=_safe_get_text(msg_node, "bot_response", ""),
                        is_synthetic=is_synth_val,
                        request_start_time=ts_dt,
                        # Campos numéricos
                        user_chars=int(_safe_get_text(msg_node, "user_chars", 0)),
                        bot_chars=int(_safe_get_text(msg_node, "bot_chars", 0)),
                        user_tokens=int(_safe_get_text(msg_node, "user_tokens", 0)),
                        bot_tokens=int(_safe_get_text(msg_node, "bot_tokens", 0)),
                        retrieval_duration_sec=float(
                            _safe_get_text(msg_node, "retrieval_duration_sec", 0.0)
                        ),
                        generation_duration_sec=float(
                            _safe_get_text(msg_node, "generation_duration_sec", 0.0)
                        ),
                        total_duration_sec=float(
                            _safe_get_text(msg_node, "total_duration_sec", 0.0)
                        ),
                    )

                    # Tratamento de timestamps opcionais
                    ret_end_str = _safe_get_text(msg_node, "retrieval_end_time")
                    if ret_end_str:
                        chat_entry.retrieval_end_time = datetime.fromisoformat(
                            ret_end_str
                        )

                    res_end_str = _safe_get_text(msg_node, "response_end_time")
                    if res_end_str:
                        chat_entry.response_end_time = datetime.fromisoformat(
                            res_end_str
                        )

                    session.add(chat_entry)
                    session.commit()
                    session.refresh(chat_entry)

                    # 3. Processar Feedback Aninhado (se houver)
                    fb_node = msg_node.find("feedback")
                    if fb_node is not None:
                        fb_ts_str = _safe_get_text(fb_node, "timestamp")
                        fb_ts = datetime.now()
                        if fb_ts_str:
                            fb_ts = datetime.fromisoformat(fb_ts_str)

                        feedback_entry = Feedback(
                            message_id=chat_entry.id,  # Link com o novo ID gerado
                            rating=_safe_get_text(fb_node, "rating", "like"),
                            comment=_safe_get_text(fb_node, "comment"),
                            timestamp=fb_ts,
                        )
                        session.add(feedback_entry)
                        session.commit()

                    imported_count += 1

            st.success("Importação finalizada!")
            c1, c2 = st.columns(2)
            c1.metric("Importados (Novos)", imported_count)
            c2.metric("Ignorados (Já existiam)", skipped_count)

        except Exception as e:
            st.error(f"Erro crítico na importação: {e}")


def run_shutdown():
    """Modo 8: Sair"""
    st.subheader("Modo 8: Sair")
    st.warning("Clicar neste botão encerrará este servidor Streamlit.")
    if st.button("Encerrar Aplicação"):
        st.success("Encerrando servidor...")
        print("Comando de encerramento recebido da UI.")
        os._exit(0)


def main():
    st.set_page_config(page_title="Auditoria Histórico", layout="wide")
    st.title("Auditoria do Histórico (SQLModel)")

    st.sidebar.title("Menu")

    # Botão de Imprimir PDF
    add_print_to_pdf_button()

    st.sidebar.markdown("---")

    options = {
        "1. Listar Sessões": run_list_sessions,
        "2. Buscar Sessão": run_search_by_session,
        "3. Ver Feedbacks (Detalhes)": run_list_feedback,
        "4. Resumo dos Feedbacks": run_feedback_summary,
        "5. Exportar CSV": run_export_csv,
        "6. Exportar XML": run_export_xml,
        "7. Importar XML": run_import_xml,
        "8. Sair": run_shutdown,
    }

    if "sb_menu" not in st.session_state:
        st.session_state["sb_menu"] = list(options.keys())[0]

    choice = st.sidebar.radio("Opções", list(options.keys()), key="sb_menu")

    options[choice]()


if __name__ == "__main__":
    main()
