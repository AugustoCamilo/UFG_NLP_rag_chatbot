# validate_evaluation.py
"""
Módulo de Dashboard de Avaliação de Métricas (Frontend de Teste).

Este script é uma aplicação Streamlit independente, projetada para
ler e visualizar os dados de avaliação.


1. Usar SQLModel.
2. Usar settings.py para configuração.
3. Exportar XML com timestamp.
4. Filtro por tipo de busca na listagem.
5. Exibição COMPLETA do conteúdo dos chunks.
"""

import streamlit as st
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
from datetime import datetime
from sqlmodel import Session, create_engine, select, func, desc

# --- Imports do Projeto ---
from ui_utils import add_print_to_pdf_button
from settings import settings
from database import ValidationRun, ValidationRetrievedChunk

# Configuração do Engine Síncrono para o Streamlit
engine = create_engine(settings.SYNC_DATABASE_URL)


def get_session():
    """Retorna uma sessão síncrona do SQLModel."""
    return Session(engine)


def _safe_get_text(element, tag, default=None):
    """Helper para ler XML."""
    found = element.find(tag)
    if found is not None and found.text is not None:
        return found.text
    return default


# --- MODO 1: RESUMO ---
def run_metrics_summary():
    st.subheader("Modo 1: Resumo das Métricas de Avaliação")
    st.info("Calcula médias de Hit Rate, MRR e Precisão@K.")

    if st.button("Calcular Resumo"):
        with get_session() as session:
            statement = select(
                ValidationRun.search_type,
                func.count(ValidationRun.id),
                func.avg(ValidationRun.hit_rate_eval),
                func.avg(ValidationRun.mrr_eval),
                func.avg(ValidationRun.precision_at_k_eval),
            ).group_by(ValidationRun.search_type)
            results = session.exec(statement).all()

            if not results:
                st.warning("Nenhuma avaliação encontrada.")
                return

            data = []
            for row in results:
                data.append(
                    {
                        "TIPO DE BUSCA": row[0],
                        "TOTAL": row[1],
                        "HIT RATE (%)": f"{row[2]*100:.2f}%",
                        "MRR MÉDIO": f"{row[3]:.4f}",
                        "PRECISÃO@K": f"{row[4]:.4f}",
                    }
                )
            st.dataframe(data, use_container_width=True)

            # --- LEGENDA ---
            st.markdown("---")
            st.header("Interpretação das Métricas")
            st.markdown(
                """
                - **Hit Rate (Taxa de Acerto):** A porcentagem de vezes que *pelo menos um* chunk correto foi retornado. (Maior é melhor)
                - **MRR (Mean Reciprocal Rank):** A média da "pontuação de ranking" do *primeiro* chunk correto. (Maior é melhor, 1.0 é perfeito)
                - **Precisão@K Média:** A proporção média de chunks corretos por rodada (ex: 0.66 = 2 de 3 chunks estavam certos). Mede a "pureza" do resultado. (Maior é melhor)
                """
            )


# --- MODO 2: LISTAGEM DETALHADA (COM FILTRO E TEXTO COMPLETO) ---
def run_list_evaluations():
    st.subheader("Modo 2: Listar Avaliações Detalhadas")

    # 1. Preparar o Filtro
    with get_session() as session:
        types_statement = select(ValidationRun.search_type).distinct()
        available_types = session.exec(types_statement).all()

    filter_options = ["Todos"] + list(available_types)
    selected_type = st.selectbox("Filtrar por Tipo de Busca:", filter_options)

    if st.button("Carregar Avaliações"):
        with get_session() as session:

            # 2. Construir a Query Dinâmica
            statement = select(ValidationRun).order_by(desc(ValidationRun.timestamp))

            if selected_type != "Todos":
                statement = statement.where(ValidationRun.search_type == selected_type)

            runs = session.exec(statement).all()

            if not runs:
                st.warning(f"Nenhuma avaliação encontrada para o tipo: {selected_type}")
                return

            st.success(f"Total de rodadas encontradas: {len(runs)}")

            for run in runs:
                hr_icon = "✅" if run.hit_rate_eval else "❌"

                with st.container(border=True):
                    st.markdown(
                        f"**ID: {run.id}** | {run.timestamp.strftime('%d/%m/%Y %H:%M:%S')} | Tipo: **{run.search_type}**"
                    )
                    st.markdown(f"> Query: *{run.query}*")

                    c1, c2, c3 = st.columns(3)
                    c1.metric("Hit Rate", hr_icon)
                    c2.metric("MRR", f"{run.mrr_eval:.4f}")
                    c3.metric("P@K", f"{run.precision_at_k_eval:.4f}")

                    # Busca chunks associados
                    chunks = session.exec(
                        select(ValidationRetrievedChunk)
                        .where(ValidationRetrievedChunk.run_id == run.id)
                        .order_by(ValidationRetrievedChunk.rank)
                    ).all()

                    st.markdown("---")
                    st.markdown("**Chunks Retornados:**")

                    for chunk in chunks:
                        color = "green" if chunk.is_correct_eval else "red"
                        correct_lbl = "SIM" if chunk.is_correct_eval else "NÃO"

                        # Cabeçalho do Chunk
                        st.markdown(
                            f"**{chunk.rank}.** :{color}[Correct: {correct_lbl}] | Score: {chunk.score:.4f} | {chunk.source} (p.{chunk.page})"
                        )

                        # Texto completo
                        st.text(chunk.chunk_content)
                        st.markdown("---")


# --- MODO 3: EXPORTAR XML ---
def run_export_xml():
    st.subheader("Modo 3: Exportar Avaliações (XML)")
    st.info("Exporta os dados para backup ou análise.")

    if st.button("Gerar Arquivo XML"):
        with get_session() as session:
            runs = session.exec(select(ValidationRun)).all()

            if not runs:
                st.error("Banco de dados vazio.")
                return

            root = ET.Element("dados_avaliacoes")
            timestamp_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            root.insert(
                0, ET.Comment(f" Exportado em: {timestamp_now} | Total: {len(runs)} ")
            )

            for run in runs:
                run_el = ET.SubElement(root, "validation_run")
                for k, v in run.model_dump().items():
                    if v is not None:
                        ET.SubElement(run_el, k).text = str(v)

                chunks = session.exec(
                    select(ValidationRetrievedChunk)
                    .where(ValidationRetrievedChunk.run_id == run.id)
                    .order_by(ValidationRetrievedChunk.rank)
                ).all()

                chunks_el = ET.SubElement(run_el, "retrieved_chunks")
                for chunk in chunks:
                    chunk_el = ET.SubElement(chunks_el, "chunk")
                    for k, v in chunk.model_dump().items():
                        if v is not None:
                            ET.SubElement(chunk_el, k).text = str(v)

            xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
            file_timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            filename = f"avaliacoes_{file_timestamp}.xml"

            with open(filename, "w", encoding="utf-8") as f:
                f.write(xml_str)

            st.success("Exportação concluída com sucesso!")
            st.code(filename, language="text")


# --- MODO 4: IMPORTAR XML ---
def run_import_xml():
    st.subheader("Modo 4: Importar Avaliações (XML)")
    st.info("Importa dados ignorando duplicatas (baseado no timestamp).")

    uploaded_file = st.file_uploader("Selecione o arquivo XML", type=["xml"])

    if uploaded_file and st.button("Iniciar Importação"):
        imported_count = 0
        skipped_count = 0

        try:
            tree = ET.parse(uploaded_file)
            root = tree.getroot()

            with get_session() as session:
                all_runs_xml = root.findall("validation_run")

                for run_node in all_runs_xml:
                    ts_str = _safe_get_text(run_node, "timestamp")
                    if not ts_str:
                        skipped_count += 1
                        continue

                    try:
                        ts_dt = datetime.fromisoformat(ts_str)
                    except ValueError:
                        ts_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")

                    existing = session.exec(
                        select(ValidationRun).where(ValidationRun.timestamp == ts_dt)
                    ).first()

                    if existing:
                        skipped_count += 1
                        continue

                    run_obj = ValidationRun(
                        timestamp=ts_dt,
                        query=_safe_get_text(run_node, "query", ""),
                        search_type=_safe_get_text(run_node, "search_type", "unknown"),
                        hit_rate_eval=int(_safe_get_text(run_node, "hit_rate_eval", 0)),
                        mrr_eval=float(_safe_get_text(run_node, "mrr_eval", 0.0)),
                        precision_at_k_eval=float(
                            _safe_get_text(run_node, "precision_at_k_eval", 0.0)
                        ),
                    )
                    session.add(run_obj)
                    session.commit()
                    session.refresh(run_obj)

                    imported_count += 1

                    chunks_node = run_node.find("retrieved_chunks")
                    if chunks_node is not None:
                        for chunk_node in chunks_node.findall("chunk"):
                            page_txt = _safe_get_text(chunk_node, "page")
                            page_val = (
                                int(page_txt)
                                if page_txt and page_txt != "None"
                                else None
                            )

                            chunk_obj = ValidationRetrievedChunk(
                                run_id=run_obj.id,
                                rank=int(_safe_get_text(chunk_node, "rank", 0)),
                                chunk_content=_safe_get_text(
                                    chunk_node, "chunk_content", ""
                                ),
                                source=_safe_get_text(chunk_node, "source", "N/A"),
                                page=page_val,
                                score=float(_safe_get_text(chunk_node, "score", 0.0)),
                                is_correct_eval=int(
                                    _safe_get_text(chunk_node, "is_correct_eval", 0)
                                ),
                            )
                            session.add(chunk_obj)
                        session.commit()

            st.success("Processo finalizado!")
            c1, c2 = st.columns(2)
            c1.metric("Importados (Novos)", imported_count)
            c2.metric("Ignorados (Duplicados)", skipped_count)

        except Exception as e:
            st.error(f"Erro na importação: {e}")


# --- MODO 5: SAIR ---
def run_shutdown():
    st.subheader("Modo 5: Encerrar Servidor")
    if st.button("Encerrar Aplicação"):
        st.warning("Encerrando...")
        os._exit(0)


# --- MAIN ---
def main():
    st.set_page_config(page_title="Auditoria de Avaliação", layout="wide")
    st.title("Ferramenta de Auditoria (SQLModel)")

    add_print_to_pdf_button()
    st.sidebar.markdown("---")

    options = {
        "1. Resumo das Métricas": run_metrics_summary,
        "2. Listar Detalhes": run_list_evaluations,
        "3. Exportar XML": run_export_xml,
        "4. Importar XML": run_import_xml,
        "5. Sair": run_shutdown,
    }

    choice = st.sidebar.radio("Menu", list(options.keys()))

    options[choice]()


if __name__ == "__main__":
    main()
