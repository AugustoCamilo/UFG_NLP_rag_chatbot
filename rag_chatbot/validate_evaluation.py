# validate_evaluation.py
import streamlit as st
import sqlite3
import os
import sys
import csv
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import pandas as pd

# Importar o arquivo de configuração do banco de dados
# para obter o caminho (DB_PATH)
import database as history_db


@st.cache_resource
def connect_to_db():
    """Conecta ao banco de dados SQLite e o armazena no cache."""
    st.write("Conectando ao banco de dados...")

    db_path = history_db.DB_PATH  #

    if not os.path.exists(db_path):  #
        st.error(f"Erro: Arquivo do banco de dados não encontrado em '{db_path}'")
        st.error(
            "Por favor, execute 'python database.py' e 'validate_vector_db.py' primeiro."
        )
        st.stop()

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.text_factory = str
        st.sidebar.success(f"Conectado ao DB.")
        return conn
    except Exception as e:
        st.error(f"Ocorreu um erro ao conectar ao banco de dados: {e}")
        st.stop()


def run_metrics_summary(conn):
    """Modo 1: Resumo das Métricas de Avaliação"""
    st.subheader("Modo 1: Resumo das Métricas de Avaliação")  #
    st.info(
        "Calcula o Hit Rate, MRR e Precisão@K médios " "com base nas avaliações salvas."
    )

    if st.button("Calcular Resumo de Métricas"):
        with st.spinner("Calculando métricas..."):
            try:

                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT 
                        search_type,
                        COUNT(*) as total_runs,
                        AVG(hit_rate_eval) as avg_hit_rate,
                        AVG(mrr_eval) as avg_mrr,
                        AVG(precision_at_k_eval) as avg_precision
                    FROM validation_runs
                    GROUP BY search_type
                    """
                )
                rows = cursor.fetchall()

                if not rows:
                    st.warning("Nenhuma avaliação encontrada no banco de dados.")
                    return

                st.success(f"Métricas calculadas para {len(rows)} tipo(s) de busca:")

                data = [
                    {
                        "TIPO DE BUSCA": row[0],
                        "TOTAL DE TESTES": row[1],
                        "TAXA DE ACERTO (Hit Rate %)": f"{float(row[2]) * 100:.2f}%",
                        "MRR MÉDIO": f"{row[3]:.4f}",
                        "PRECISÃO@K MÉDIA": f"{row[4]:.4f}",
                    }
                    for row in rows
                ]  #
                st.dataframe(data, use_container_width=True)

                st.markdown("---")
                st.header("Interpretação")
                st.markdown(
                    """
                    - **Hit Rate (Taxa de Acerto):** A porcentagem de vezes que *pelo menos um* chunk correto foi retornado. (Maior é melhor)
                    - **MRR (Mean Reciprocal Rank):** A média da "pontuação de ranking" do *primeiro* chunk correto. (Maior é melhor, 1.0 é perfeito)
                    - **Precisão@K Média:** A proporção média de chunks corretos por rodada (ex: 0.66 = 2 de 3 chunks estavam certos). Mede a "pureza" do resultado. (Maior é melhor)
                    """
                )

            except Exception as e:
                st.error(f"Erro ao calcular métricas: {e}")


def run_list_evaluations(conn):
    """Modo 2: Listar Avaliações Detalhadas"""
    st.subheader("Modo 2: Listar Avaliações Detalhadas")
    st.info(
        "Exibe cada rodada de validação e os chunks que foram marcados como corretos."
    )

    if st.button("Carregar Todas as Avaliações"):
        with st.spinner("Consultando avaliações..."):
            try:
                cursor = conn.cursor()

                # Query para buscar todas as rodadas
                cursor.execute(
                    """
                    SELECT id, timestamp, query, search_type, 
                           hit_rate_eval, mrr_eval, precision_at_k_eval
                    FROM validation_runs
                    ORDER BY timestamp DESC
                    """
                )
                runs = cursor.fetchall()

                if not runs:
                    st.warning("Nenhuma avaliação (rodada) encontrada.")
                    return

                # --- REQUISITO 1: Manter o total ---
                st.success(f"Total de rodadas de avaliação: {len(runs)}")

                # --- REQUISITO 2: Tabela de Resumo por Tipo ---
                cursor.execute(
                    """
                    SELECT search_type, COUNT(*) as total_runs
                    FROM validation_runs
                    GROUP BY search_type
                    """
                )
                summary_rows = cursor.fetchall()

                if summary_rows:
                    summary_data = [
                        {
                            "TIPO DE BUSCA": row[0],
                            "TOTAL DE AVALIAÇÕES": row[1],
                        }
                        for row in summary_rows
                    ]
                    st.markdown("**Total de Avaliações por Tipo:**")
                    st.dataframe(summary_data, use_container_width=True)

                st.divider()
                st.markdown("### Detalhamento das Rodadas")

                # Query para buscar os chunks (prepara para consulta)
                chunk_query = """
                    SELECT rank, chunk_content, source, page, score, is_correct_eval
                    FROM validation_retrieved_chunks
                    WHERE run_id = ?
                    ORDER BY rank ASC
                """  #

                # Exibe cada rodada
                for run in runs:  #
                    (run_id, ts, query, s_type, hr, mrr, p_at_k) = run

                    # Converte os valores para os tipos corretos
                    run_id = int(run_id)
                    query = str(query)
                    s_type = str(s_type)
                    hr = int(hr)
                    mrr = float(mrr)
                    p_at_k = float(p_at_k)

                    hr_text = "✅ Sucesso" if hr == 1 else "❌ Falha"

                    with st.container(border=True):
                        # Linha de ID (mantida)
                        st.markdown(
                            f"**ID da Rodada: {run_id}** | {ts} | **Tipo: {s_type}**"
                        )

                        # --- REQUISITO 3: Destaque da Query ---
                        st.markdown("**Query:**")
                        st.markdown(f"> *{query}*")  # Usando blockquote e itálico

                        # --- REQUISITO 4: Destaque das Métricas ---
                        st.markdown("**Métricas da Rodada:**")
                        col1, col2, col3 = st.columns(3)
                        col1.metric(
                            label="Taxa de Acerto (Hit Rate)",
                            value=hr_text,
                            help="Indica se pelo menos um chunk relevante foi encontrado nesta rodada.",
                        )
                        col2.metric(label="MRR (Pontuação)", value=f"{mrr:.4f}")
                        col3.metric(label="Precisão@K", value=f"{p_at_k:.4f}")

                        st.markdown("**Chunks Retornados:**")

                        # Busca os chunks para esta rodada
                        cursor.execute(chunk_query, (run_id,))
                        chunks = cursor.fetchall()

                        for chunk in chunks:
                            (rank, content, source, page, score, is_correct) = chunk

                            rank = int(rank)
                            content = str(content)
                            source = str(source)
                            score = float(
                                score
                            )  # O diagnóstico provou que isso é um float
                            is_correct = int(is_correct)

                            page_str = str(page) if page is not None else "N/A"

                            # --- REQUISITO 5: Destaque do "Correto" ---
                            correct_text = "SIM" if is_correct == 1 else "NÃO"
                            correct_color = "green" if is_correct == 1 else "red"

                            st.markdown(
                                f"  **{rank}.** <font color='{correct_color}'>**(Correto: {correct_text})**</font> | [Score: {score:.4f}] - *{source}, p.{page}*",
                                unsafe_allow_html=True,
                            )
                            st.text(f"     {content[:150]}...")  #

            except Exception as e:
                st.error(f"Erro ao listar avaliações: {e}")  #


# --- FIM DA FUNÇÃO ATUALIZADA ---


def run_export_xml(conn):
    """Modo 3: Exportar Avaliações para XML"""
    # (Esta função permanece inalterada)
    st.subheader("Modo 3: Exportar Avaliações (XML)")  #
    st.info(
        "Exporta um XML completo contendo todas as rodadas de validação e "
        "os chunks recuperados. O arquivo será salvo na pasta deste script."
    )  #

    if st.button("Gerar Arquivo 'avaliacoes_exportadas.xml'"):  #
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  #
        output_filename = "avaliacoes_exportadas.xml"  #
        output_path = os.path.join(SCRIPT_DIR, output_filename)  #

        with st.spinner("Exportando avaliações para XML..."):  #
            try:
                cursor = conn.cursor()  #
                # 1. Obter todas as rodadas
                cursor.execute(
                    "SELECT * FROM validation_runs ORDER BY timestamp ASC"
                )  #
                runs = cursor.fetchall()  #
                run_headers = [desc[0] for desc in cursor.description]  #

                if not runs:  #
                    st.error("Nada para exportar, nenhuma avaliação encontrada.")
                    return

                # 2. Obter todos os chunks
                cursor.execute(
                    "SELECT * FROM validation_retrieved_chunks ORDER BY run_id, rank ASC"
                )  #
                chunks = cursor.fetchall()  #
                chunk_headers = [desc[0] for desc in cursor.description]  #

                # Organiza os chunks por run_id para fácil acesso
                chunks_by_run = {}  #
                for chunk in chunks:  #
                    chunk_dict = dict(zip(chunk_headers, chunk))  #
                    run_id = chunk_dict["run_id"]  #
                    if run_id not in chunks_by_run:  #
                        chunks_by_run[run_id] = []  #
                    chunks_by_run[run_id].append(chunk_dict)  #

                # 3. Construir o XML
                root = ET.Element("dados_avaliacoes")  #
                now = datetime.now()  #
                timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")  #
                comment_text = f" Exportação gerada em: {timestamp_str}. Total de rodadas: {len(runs)} "  #
                root.insert(0, ET.Comment(comment_text))  #

                for run in runs:  #
                    run_dict = dict(zip(run_headers, run))  #
                    run_id = run_dict["id"]  #

                    # Nó da Rodada
                    run_el = ET.SubElement(root, "validation_run")  #
                    for key, val in run_dict.items():  #
                        el = ET.SubElement(run_el, key)  #
                        el.text = str(val)  #

                    # Nós dos Chunks
                    chunks_el = ET.SubElement(run_el, "retrieved_chunks")  #
                    if run_id in chunks_by_run:  #
                        for chunk_dict in chunks_by_run[run_id]:  #
                            chunk_el = ET.SubElement(chunks_el, "chunk")  #
                            for key, val in chunk_dict.items():  #
                                el = ET.SubElement(chunk_el, key)  #
                                el.text = str(val)  #

                # 4. Formatar e Salvar
                xml_string = ET.tostring(root, "utf-8")  #
                parsed_string = minidom.parseString(xml_string)  #
                pretty_xml = parsed_string.toprettyxml(indent="  ", encoding="utf-8")  #

                with open(output_path, "wb") as f:  #
                    f.write(pretty_xml)  #

                st.success(f"\nSucesso! {len(runs)} rodadas exportadas para:")  #
                st.code(output_path, language="bash")  #

            except Exception as e:
                st.error(f"\nErro ao salvar o arquivo XML: {e}")  #


def run_shutdown():
    """Modo 4: Encerrar"""
    # (Esta função permanece inalterada)
    st.subheader("Modo 4: Encerrar Servidor")  #
    st.warning("Clicar neste botão encerrará este servidor Streamlit.")  #

    if st.button("Encerrar Aplicação"):  #
        st.success("Encerrando servidor...")  #
        print("Comando de encerramento recebido da UI.")  #
        os._exit(0)  # Força a parada do processo Python


def main():
    st.set_page_config(page_title="Auditoria de Avaliação", layout="wide")  #
    st.title("Ferramenta de Auditoria de Métricas (HR & MRR)")  #
    st.caption(
        "Esta interface consulta as tabelas 'validation_runs' do 'chat_solution.db'."
    )  #

    conn = connect_to_db()  #

    st.sidebar.title("Opções de Auditoria")  #
    opcoes = [
        "1. Resumo das Métricas (HR & MRR)",
        "2. Listar Avaliações Detalhadas",
        "3. Exportar Avaliações (XML)",
        "4. Encerrar Servidor",
    ]  #
    modo = st.sidebar.radio(
        "Selecione uma operação:", opcoes, label_visibility="collapsed"
    )  #

    if modo == opcoes[0]:  #
        run_metrics_summary(conn)  #
    elif modo == opcoes[1]:  #
        run_list_evaluations(conn)  #
    elif modo == opcoes[2]:  #
        run_export_xml(conn)  #
    elif modo == opcoes[3]:  #
        run_shutdown()  #


if __name__ == "__main__":
    main()  #
