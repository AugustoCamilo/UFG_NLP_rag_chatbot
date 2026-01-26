# validate_history_db.py
"""
Módulo de Dashboard de Auditoria do Histórico de Produção.

Permite a visualização detalhada de sessões de chat, feedbacks dos usuários,
métricas consolidadas e cruzamento de dados com a base de validação.
"""

import streamlit as st
import pandas as pd
import os
import xml.etree.ElementTree as ET
import altair as alt
from xml.dom import minidom
from datetime import datetime
from sqlmodel import Session, create_engine, select, func, desc, col

# --- Imports do Projeto ---
from settings import settings
from ui_utils import add_print_to_pdf_button
from database import ChatHistory, Feedback, ValidationRun, ValidationRetrievedChunk

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
    st.session_state["sb_menu"] = "4. Buscar Sessão"


def run_list_sessions():
    """Modo: Listar Todas as Sessões"""
    st.subheader("Listar Todas as Sessões")

    if st.button("Carregar Resumo das Sessões"):
        with st.spinner("Consultando sessões via SQLModel..."):
            with get_session_sync() as session:
                statement = (
                    select(
                        ChatHistory.session_id,
                        func.count(ChatHistory.id).label("msg_count"),
                        func.max(ChatHistory.response_end_time).label("last_activity"),
                        func.avg(ChatHistory.total_duration_sec).label("avg_duration"),
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
    """Modo: Buscar por Sessão"""
    st.subheader("Buscar Histórico por Sessão")

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
    """Modo: Ver Avaliações Detalhadas"""
    st.subheader("Ver Avaliações (Detalhado)")

    # --- FILTROS ---
    c1, c2 = st.columns(2)
    with c1:
        origin_filter = st.selectbox(
            "Filtrar por Origem:", ["Todos", "Usuário Real", "Teste Sintético"]
        )
    with c2:
        metric_filter = st.selectbox(
            "Filtrar por Métrica:", ["Todos", "👍 Likes", "👎 Dislikes", "⬜ Em Branco"]
        )

    if st.button("Carregar Lista de Feedbacks"):
        with get_session_sync() as session:
            # Construção da Query: ChatHistory LEFT JOIN Feedback
            # Usamos outerjoin para garantir que trazemos mensagens SEM feedback (Em Branco)
            statement = (
                select(ChatHistory, Feedback)
                .outerjoin(Feedback, ChatHistory.id == Feedback.message_id)
                .order_by(desc(ChatHistory.request_start_time))
            )

            # 1. Aplicar Filtro de Origem
            if origin_filter == "Usuário Real":
                statement = statement.where(ChatHistory.is_synthetic == False)
            elif origin_filter == "Teste Sintético":
                statement = statement.where(ChatHistory.is_synthetic == True)

            # 2. Aplicar Filtro de Métrica
            if metric_filter == "👍 Likes":
                statement = statement.where(Feedback.rating == "like")
            elif metric_filter == "👎 Dislikes":
                statement = statement.where(Feedback.rating == "dislike")
            elif metric_filter == "⬜ Em Branco":
                statement = statement.where(Feedback.id == None)

            # Executa a query
            results = session.exec(statement).all()

            if not results:
                st.warning("Nenhum registro encontrado com os filtros selecionados.")
                return

            st.success(f"Encontrados {len(results)} registros.")

            for history, feedback in results:
                # Determina o ícone/texto da avaliação
                if feedback:
                    icon = "👍" if feedback.rating == "like" else "👎"
                    rating_text = feedback.rating.upper()
                    ts = feedback.timestamp
                    comment = feedback.comment
                else:
                    icon = "⬜"
                    rating_text = "EM BRANCO"
                    ts = history.request_start_time
                    comment = None

                # Definição do Label de Origem
                if history.is_synthetic:
                    origin_label = "🧪 Teste Sintético"
                    origin_color = "orange"
                else:
                    origin_label = "👤 Usuário Real"
                    origin_color = "blue"

                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(f"**{icon} {rating_text}** | {ts}")
                    c2.markdown(f":{origin_color}[**{origin_label}**]")

                    if comment:
                        st.info(f"Comentário: {comment}")
                    st.text(f"Q: {history.user_message}")
                    st.text(f"A: {history.bot_response}")

                    # --- ÁREA DE CONTEXTO CRUZADO (VALIDATION RUNS) ---
                    with st.expander(
                        "🔍 Visualizar Contexto (Via Validação Cruzada)", expanded=False
                    ):

                        # 1. Definir Tipos de Busca Permitidos (Regras de Negócio)
                        target_search_types = []
                        if origin_filter == "Teste Sintético":
                            target_search_types = ["reranked_AB"]
                        elif origin_filter == "Usuário Real":
                            target_search_types = ["reranked_USER"]
                        else:  # Todos
                            target_search_types = ["reranked_USER", "reranked_AB"]

                        # 2. Busca na Tabela de Validação
                        # Filtra por Query Exata E pelo Tipo definido acima
                        val_run = session.exec(
                            select(ValidationRun)
                            .where(ValidationRun.query == history.user_message)
                            .where(ValidationRun.search_type.in_(target_search_types))
                            .order_by(desc(ValidationRun.timestamp))
                        ).first()

                        if val_run:
                            st.success(
                                f"Validação Cruzada Encontrada! (Tipo: {val_run.search_type})"
                            )
                            st.caption(f"ID: {val_run.id} | Data: {val_run.timestamp}")

                            # Métricas da Validação
                            m1, m2, m3 = st.columns(3)
                            hr_icon = "✅" if val_run.hit_rate_eval else "❌"
                            m1.metric("Hit Rate (Gabarito)", hr_icon)
                            m2.metric("MRR", f"{val_run.mrr_eval:.4f}")
                            m3.metric("P@K", f"{val_run.precision_at_k_eval:.4f}")

                            # Carrega Chunks
                            chunks = session.exec(
                                select(ValidationRetrievedChunk)
                                .where(ValidationRetrievedChunk.run_id == val_run.id)
                                .order_by(ValidationRetrievedChunk.rank)
                            ).all()

                            st.markdown("---")
                            st.markdown("**Chunks Retornados:**")

                            for chunk in chunks:
                                color = "green" if chunk.is_correct_eval else "red"
                                correct_lbl = "SIM" if chunk.is_correct_eval else "NÃO"

                                st.markdown(
                                    f"**{chunk.rank}.** :{color}[Relevante: {correct_lbl}] | Score: {chunk.score:.4f} | {chunk.source} (p.{chunk.page})"
                                )
                                st.text(chunk.chunk_content)
                                st.markdown("---")
                        else:
                            st.warning(
                                "⚠️ Nenhuma validação compatível foi encontrada para esta pergunta."
                            )
                            st.markdown(f"**Critérios de busca:**")
                            st.markdown(f"- Query exata: *'{history.user_message}'*")
                            st.markdown(f"- Tipos procurados: `{target_search_types}`")
                            st.info(
                                "Dica: Use o 'validate_vector_db.py' para criar o gabarito desta pergunta."
                            )


def run_feedback_summary():
    """Modo: Resumo dos Feedbacks"""
    st.subheader("Resumo dos Feedbacks (Estatísticas)")
    st.info(
        "Estatísticas consolidadas de satisfação e performance, separadas por origem e métrica."
    )

    # --- FILTRO DE ORIGEM ---
    origin_filter = st.selectbox(
        "Filtrar Dados por Origem:", ["Todos", "Usuário Real", "Teste Sintético"]
    )

    if st.button("Calcular Estatísticas"):
        with get_session_sync() as session:

            # Definição base das origens
            all_origins = [
                {"label": "👤 Usuário Real", "is_synthetic": False},
                {"label": "🧪 Teste Sintético", "is_synthetic": True},
            ]

            # Aplica o filtro
            if origin_filter == "Todos":
                origins_to_check = all_origins
            elif origin_filter == "Usuário Real":
                origins_to_check = [all_origins[0]]
            else:  # Teste Sintético
                origins_to_check = [all_origins[1]]

            consolidated_data = []
            charts_payload = []  # Para armazenar dados para os gráficos

            for origin in origins_to_check:
                is_synth = origin["is_synthetic"]
                label_origin = origin["label"]

                # --- HELPER: Calcula médias para um subset específico ---
                def get_avg_times(rating_filter=None, only_blanks=False):
                    """
                    Calcula médias de tempo filtrando por rating.
                    rating_filter: 'like' ou 'dislike'
                    only_blanks: True para pegar mensagens sem feedback
                    """
                    query = select(
                        func.avg(ChatHistory.retrieval_duration_sec),
                        func.avg(ChatHistory.generation_duration_sec),
                        func.avg(ChatHistory.total_duration_sec),
                    ).where(ChatHistory.is_synthetic == is_synth)

                    if only_blanks:
                        # Left Join para encontrar onde Feedback é Nulo
                        query = query.outerjoin(
                            Feedback, ChatHistory.id == Feedback.message_id
                        ).where(Feedback.id == None)
                    elif rating_filter:
                        # Inner Join para filtrar por rating específico
                        query = query.join(
                            Feedback, ChatHistory.id == Feedback.message_id
                        ).where(Feedback.rating == rating_filter)

                    # Executa a query
                    result = session.exec(query).one()

                    # Trata None (caso não haja registros no filtro)
                    return (
                        result[0] if result[0] else 0.0,
                        result[1] if result[1] else 0.0,
                        result[2] if result[2] else 0.0,
                    )

                # 1. Total de Interações (Geral da Origem)
                total_msgs = session.exec(
                    select(func.count(ChatHistory.id)).where(
                        ChatHistory.is_synthetic == is_synth
                    )
                ).one()

                if total_msgs == 0:
                    continue

                # 2. Likes (Contagem e Médias)
                likes = session.exec(
                    select(func.count(Feedback.id))
                    .join(ChatHistory, Feedback.message_id == ChatHistory.id)
                    .where(Feedback.rating == "like")
                    .where(ChatHistory.is_synthetic == is_synth)
                ).one()
                avg_ret_like, avg_gen_like, avg_tot_like = get_avg_times(
                    rating_filter="like"
                )

                # 3. Dislikes (Contagem e Médias)
                dislikes = session.exec(
                    select(func.count(Feedback.id))
                    .join(ChatHistory, Feedback.message_id == ChatHistory.id)
                    .where(Feedback.rating == "dislike")
                    .where(ChatHistory.is_synthetic == is_synth)
                ).one()
                avg_ret_dislike, avg_gen_dislike, avg_tot_dislike = get_avg_times(
                    rating_filter="dislike"
                )

                # 4. Em Branco (Contagem e Médias)
                total_feedbacks = likes + dislikes
                blanks = total_msgs - total_feedbacks
                if blanks < 0:
                    blanks = 0
                avg_ret_blank, avg_gen_blank, avg_tot_blank = get_avg_times(
                    only_blanks=True
                )

                # 5. Médias Gerais (TOTAL da Origem)
                avg_ret_total, avg_gen_total, avg_tot_total = get_avg_times()

                # --- Cálculos Percentuais ---
                pct_likes = (likes / total_msgs) * 100
                pct_dislikes = (dislikes / total_msgs) * 100
                pct_blanks = (blanks / total_msgs) * 100

                # Helper para criar a linha da tabela formatada
                def create_row(metric, total, pct, ret_time, gen_time, tot_time):
                    return {
                        "Origem": label_origin,
                        "Métrica": metric,
                        "Total": total,
                        "Porcentagem": pct,
                        "Tempo médio RAG": f"{ret_time:.2f}s",
                        "Tempo médio LLM": f"{gen_time:.2f}s",
                        "Tempo médio Total": f"{tot_time:.2f}s",
                    }

                # Adicionar linhas à tabela com as médias ESPECÍFICAS
                consolidated_data.append(
                    create_row(
                        "👍 Likes",
                        likes,
                        f"{pct_likes:.2f}%",
                        avg_ret_like,
                        avg_gen_like,
                        avg_tot_like,
                    )
                )
                consolidated_data.append(
                    create_row(
                        "👎 Dislikes",
                        dislikes,
                        f"{pct_dislikes:.2f}%",
                        avg_ret_dislike,
                        avg_gen_dislike,
                        avg_tot_dislike,
                    )
                )
                consolidated_data.append(
                    create_row(
                        "⬜ Em Branco",
                        blanks,
                        f"{pct_blanks:.2f}%",
                        avg_ret_blank,
                        avg_gen_blank,
                        avg_tot_blank,
                    )
                )
                consolidated_data.append(
                    create_row(
                        "TOTAL",
                        total_msgs,
                        "100%",
                        avg_ret_total,
                        avg_gen_total,
                        avg_tot_total,
                    )
                )

                # Dados para o Gráfico
                charts_payload.append(
                    {
                        "origin": label_origin,
                        "data": pd.DataFrame(
                            {
                                "Categoria": ["Likes", "Dislikes", "Em Branco"],
                                "Quantidade": [likes, dislikes, blanks],
                                "Porcentagem": [
                                    likes / total_msgs,
                                    dislikes / total_msgs,
                                    blanks / total_msgs,
                                ],
                            }
                        ),
                    }
                )

            if not consolidated_data:
                st.warning(f"Nenhum dado encontrado para o filtro: {origin_filter}.")
                return

            # Exibir Tabela
            st.markdown("### 📋 Tabela de Dados e Performance")
            df = pd.DataFrame(consolidated_data)

            # Ordenação das colunas
            cols_order = [
                "Origem",
                "Métrica",
                "Total",
                "Porcentagem",
                "Tempo médio RAG",
                "Tempo médio LLM",
                "Tempo médio Total",
            ]
            df = df[cols_order]

            st.table(df)

            # --- LEGENDA DESCRITIVA ---
            with st.expander(
                "ℹ️ Legenda das Colunas (Entenda os dados)", expanded=False
            ):
                st.markdown(
                    """
                * **Origem:** Tipo de interação (Usuário Real ou Teste Sintético).
                * **Métrica:** Categoria da avaliação (Like, Dislike, Em Branco).
                * **Tempo médio RAG:** Tempo médio gasto na etapa de busca vetorial e re-ranking (Recuperação de Contexto) para este grupo.
                * **Tempo médio LLM:** Tempo médio de processamento do modelo (Gemini) para gerar a resposta final para este grupo.
                * **Tempo médio Total:** Tempo total de ponta a ponta percebido (Latência Total) para este grupo.
                * **Os tempos médios são calculados separadamente para cada métrica, permitindo uma análise granular da performance.**
                * **A unidade de medida de tempo é segundos.**
                """
                )

            st.divider()

            # --- CSS PARA IMPRESSÃO ---
            st.markdown(
                """
            <style>
            @media print {
                .page-break { 
                    page-break-before: always; 
                    margin-top: 2rem;
                    display: block;
                }
                div[data-baseweb="select"] > div,
                div[data-baseweb="base-input"] {
                    background-color: #ffffff !important;
                    border: 1px solid #999999 !important;
                    color: #000000 !important;
                    -webkit-print-color-adjust: exact;
                }
                div[data-baseweb="select"] span, 
                div[data-baseweb="select"] div {
                    color: #000000 !important;
                }
            }
            </style>
            <div class="page-break"></div>
            """,
                unsafe_allow_html=True,
            )

            # Exibir Gráficos
            st.markdown("### 📊 Visualização Gráfica")

            if charts_payload:
                cols = st.columns(len(charts_payload))

                for idx, item in enumerate(charts_payload):
                    with cols[idx]:
                        st.markdown(f"**{item['origin']}**")

                        # 1. Base SEM propriedade de background
                        base = alt.Chart(item["data"]).encode(
                            theta=alt.Theta("Quantidade", stack=True)
                        )

                        # 2. Camada Pie (Arcos)
                        pie = base.mark_arc(outerRadius=100).encode(
                            color=alt.Color(
                                "Categoria",
                                scale=alt.Scale(
                                    domain=["Likes", "Dislikes", "Em Branco"],
                                    range=["#28a745", "#dc3545", "#eaeaea"],
                                ),
                                legend=alt.Legend(
                                    orient="bottom",
                                    direction="horizontal",
                                    titleColor="black",
                                    labelColor="black",
                                    titleFontWeight="bold",
                                ),
                            ),
                            tooltip=[
                                "Categoria",
                                "Quantidade",
                                alt.Tooltip("Porcentagem", format=".1%"),
                            ],
                        )

                        # 3. Camada Texto (Labels)
                        text = base.mark_text(radius=120).encode(
                            text=alt.Text("Porcentagem", format=".1%"),
                            order=alt.Order("Quantidade", sort="descending"),
                            color=alt.value("black"),
                        )

                        # 4. Combinação
                        final_chart = (pie + text).properties(background="white")

                        st.altair_chart(final_chart, use_container_width=True)


def run_export_csv():
    """Modo: Exportar para CSV"""
    st.subheader("Exportar Histórico Completo (CSV)")

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
    """Modo: Exportar XML"""
    st.subheader("Exportar Histórico (XML)")
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
            filename = f"historico_chat_validacao_{file_timestamp}.xml"

            with open(filename, "w", encoding="utf-8") as f:
                f.write(xml_str)

            st.success("Exportação XML concluída!")
            st.code(filename, language="text")


def run_import_xml():
    """Modo: Importar XML"""
    st.subheader("Importar Histórico (XML)")
    st.info(
        "Importa mensagens e feedbacks. Evita duplicatas baseando-se no ID da Sessão + Timestamp."
    )

    uploaded_file = st.file_uploader(
        "Selecione arquivo XML (historico_chat_validacao_*.xml)", type=["xml"]
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
    """Modo: Sair"""
    st.subheader("Sair")
    st.warning("Clicar neste botão encerrará este servidor Streamlit.")
    if st.button("Encerrar Aplicação"):
        st.success("Encerrando servidor...")
        print("Comando de encerramento recebido da UI.")
        os._exit(0)


def main():
    st.set_page_config(page_title="Auditoria Histórico", layout="wide")
    st.title("Auditoria do Histórico do Chatbot RAG")

    st.sidebar.title("Menu")

    # Botão de Imprimir PDF
    add_print_to_pdf_button()

    st.sidebar.markdown("---")

    options = {
        "1. Resumo dos Feedbacks": run_feedback_summary,
        "2. Ver Feedbacks (Detalhes)": run_list_feedback,
        "3. Listar Sessões": run_list_sessions,
        "4. Buscar Sessão": run_search_by_session,
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
