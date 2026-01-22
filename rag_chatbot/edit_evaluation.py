# edit_evaluation.py
"""
Módulo de Edição e Recálculo de Métricas (Curadoria).

Este script permite ao avaliador humano corrigir classificações
(Correto/Incorreto) de avaliações passadas.
Ao salvar, o sistema recalcula automaticamente: Hit Rate, MRR e P@K.

Atualizado para:
1. Filtro por Tipo de Busca.
2. Filtro por Hit Rate (Sucesso/Falha).
"""

import streamlit as st
from sqlmodel import Session, create_engine, select, desc
import os

# --- Imports do Projeto ---
from settings import settings
from ui_utils import add_print_to_pdf_button
from database import ValidationRun, ValidationRetrievedChunk

# Configuração do Engine
engine = create_engine(settings.SYNC_DATABASE_URL)


def get_session():
    """Retorna uma sessão síncrona do SQLModel."""
    return Session(engine)


def recalculate_metrics(session, run_id, chunk_updates):
    """
    Núcleo lógico: Atualiza os chunks e recalcula as métricas da Rodada (Run).
    """
    # 1. Buscar a Rodada e os Chunks atuais
    run = session.get(ValidationRun, run_id)
    if not run:
        return False

    chunks = session.exec(
        select(ValidationRetrievedChunk)
        .where(ValidationRetrievedChunk.run_id == run_id)
        .order_by(ValidationRetrievedChunk.rank)
    ).all()

    # 2. Atualizar o status dos Chunks no Banco
    for chunk in chunks:
        if chunk.id in chunk_updates:
            new_status = 1 if chunk_updates[chunk.id] else 0
            chunk.is_correct_eval = new_status
            session.add(chunk)

    # 3. Recalcular Métricas
    total_correct = sum(c.is_correct_eval for c in chunks)
    new_hit_rate = 1 if total_correct > 0 else 0

    k = len(chunks)
    new_precision = (total_correct / k) if k > 0 else 0.0

    new_mrr = 0.0
    for chunk in chunks:
        if chunk.is_correct_eval == 1:
            new_mrr = 1.0 / chunk.rank
            break

    # 4. Atualizar a Rodada
    run.hit_rate_eval = new_hit_rate
    run.mrr_eval = new_mrr
    run.precision_at_k_eval = new_precision

    session.add(run)
    session.commit()
    return True


def run_editor():
    st.subheader("Editor de Validação (Curadoria)")
    st.info(
        "Altere a avaliação dos chunks. O sistema recalculará as métricas automaticamente ao salvar."
    )

    # --- 1. Filtros ---
    with get_session() as session:
        types_statement = select(ValidationRun.search_type).distinct()
        available_types = session.exec(types_statement).all()

    # Opções dos Filtros
    filter_options_type = ["Todos"] + list(available_types)
    filter_options_hit = ["Todos", "Sucesso (Hit Rate = 1)", "Falha (Hit Rate = 0)"]

    c1, c2 = st.columns(2)
    with c1:
        selected_type = st.selectbox("Filtrar por Tipo:", filter_options_type)
    with c2:
        selected_hit = st.selectbox("Filtrar por Hit Rate:", filter_options_hit)

    # --- 2. Listagem ---
    with get_session() as session:
        statement = select(ValidationRun).order_by(desc(ValidationRun.timestamp))

        # Aplica Filtro de Tipo
        if selected_type != "Todos":
            statement = statement.where(ValidationRun.search_type == selected_type)

        # Aplica Filtro de Hit Rate
        if selected_hit == "Sucesso (Hit Rate = 1)":
            statement = statement.where(ValidationRun.hit_rate_eval == 1)
        elif selected_hit == "Falha (Hit Rate = 0)":
            statement = statement.where(ValidationRun.hit_rate_eval == 0)

        runs = session.exec(statement).all()

        if not runs:
            st.warning("Nenhuma avaliação encontrada com os filtros selecionados.")
            return

        st.success(f"Encontradas {len(runs)} avaliações.")
        st.divider()

        # Iterar sobre as rodadas (Runs)
        for run in runs:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**Query:** {run.query}")
                c2.caption(f"{run.timestamp.strftime('%d/%m %H:%M')} | ID: {run.id}")

                m1, m2, m3, m4 = st.columns(4)
                m1.markdown(f"**Tipo:** `{run.search_type}`")
                m2.metric("Hit Rate", "✅" if run.hit_rate_eval else "❌")
                m3.metric("MRR", f"{run.mrr_eval:.4f}")
                m4.metric("P@K", f"{run.precision_at_k_eval:.4f}")

                # --- ÁREA DE EDIÇÃO ---
                with st.expander("✏️ Editar Avaliação desta Query"):
                    chunks = session.exec(
                        select(ValidationRetrievedChunk)
                        .where(ValidationRetrievedChunk.run_id == run.id)
                        .order_by(ValidationRetrievedChunk.rank)
                    ).all()

                    with st.form(key=f"form_edit_{run.id}"):
                        st.markdown("##### Avalie a relevância de cada chunk:")

                        chunk_updates = {}

                        for chunk in chunks:
                            is_checked = bool(chunk.is_correct_eval)
                            col_chk, col_txt = st.columns([1, 10])

                            with col_chk:
                                new_state = st.checkbox(
                                    "Correto?", value=is_checked, key=f"chk_{chunk.id}"
                                )
                                chunk_updates[chunk.id] = new_state

                            with col_txt:
                                color = "green" if new_state else "red"
                                st.markdown(
                                    f"**Rank {chunk.rank}** (Score: {chunk.score:.4f})"
                                )
                                st.caption(f"Fonte: {chunk.source} | Pág: {chunk.page}")
                                st.text(chunk.chunk_content)
                                st.markdown("---")

                        if st.form_submit_button("💾 Salvar Alterações e Recalcular"):
                            with st.spinner("Recalculando métricas..."):
                                success = recalculate_metrics(
                                    session, run.id, chunk_updates
                                )
                                if success:
                                    st.success("Atualizado com sucesso!")
                                    st.rerun()
                                else:
                                    st.error("Erro ao atualizar.")


def run_shutdown():
    st.subheader("Sair")
    if st.button("Encerrar Aplicação"):
        os._exit(0)


def main():
    st.set_page_config(page_title="Editor de Validação", layout="wide")
    st.title("Editor e Corretor de Validação")

    st.sidebar.title("Menu")
    add_print_to_pdf_button()
    st.sidebar.markdown("---")

    options = {"1. Editar Avaliações": run_editor, "2. Sair": run_shutdown}

    if "sb_menu_edit" not in st.session_state:
        st.session_state["sb_menu_edit"] = list(options.keys())[0]

    choice = st.sidebar.radio("Opções", list(options.keys()), key="sb_menu_edit")

    options[choice]()


if __name__ == "__main__":
    main()
