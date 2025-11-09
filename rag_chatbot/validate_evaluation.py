# validate_evaluation.py
"""
Módulo de Dashboard de Avaliação de Métricas (Frontend de Teste).

Este script é uma aplicação Streamlit independente, projetada para
*ler* e *visualizar* os dados de avaliação que foram salvos
pelo script `validate_vector_db.py`.

Enquanto `validate_vector_db.py` é a ferramenta de *entrada* de dados
(onde o avaliador humano submete os testes), este script é
a ferramenta de *análise* (o dashboard onde os resultados
agregados são exibidos).

Ele se conecta ao mesmo banco de dados (`chat_solution.db`)
e foca na leitura das tabelas `validation_runs` e
`validation_retrieved_chunks`.

---
### Funcionalidades Principais (Modos)
---

A aplicação é dividida em cinco modos principais, selecionáveis
na barra lateral:

1.  **Resumo das Métricas (HR, MRR & P@K):**
    * Executa a função `run_metrics_summary`.
    * Calcula as médias (`AVG`) das três métricas principais
        (Hit Rate, MRR, Precisão@K).
    * Agrupa os resultados por `search_type`, permitindo uma
        comparação direta de performance entre a busca
        'vector_only' e 'reranked'.
    * Exibe os resultados em um `st.dataframe`.

2.  **Listar Avaliações Detalhadas:**
    * Executa a função `run_list_evaluations`.
    * Exibe *cada rodada* de avaliação individualmente.
    * Para cada rodada, exibe a Query, as três métricas
        calculadas (usando `st.metric`) e, em seguida,
        consulta e exibe os chunks que foram retornados.
    * Destaca visualmente os chunks marcados como corretos
        (verde/vermelho).
    * *Nota de Implementação:* Esta função inclui conversão
        de tipo explícita (ex: `float(score)`) para
        garantir que os dados lidos do SQLite sejam
        corretamente formatados.

3.  **Exportar Avaliações (XML):**
    * Executa a função `run_export_xml`.
    * Lê *todos* os dados das tabelas `validation_runs` e
        `validation_retrieved_chunks`.
    * Constrói um arquivo XML estruturado contendo todos os dados
        de avaliação para análise externa ou backup.

4.  **Importar Avaliações (XML):** (NOVO)
    * Executa a função `run_import_xml`.
    * Permite o upload de um arquivo XML (gerado pelo Modo 3).
    * Faz o parse do XML, verifica se o 'timestamp' de cada rodada
        já existe no banco, e insere *apenas* os registros novos,
        ignorando duplicados. Ao final, exibe um resumo.

5.  **Encerrar Servidor:**
    * Uma função de conveniência (`run_shutdown`) que chama
        `os._exit(0)` para parar o processo do Streamlit.
"""


import streamlit as st
import sqlite3
import os
import sys
import csv
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from streamlit.components.v1 import html
import pandas as pd

# Importar o arquivo de configuração do banco de dados
# para obter o caminho (DB_PATH)
import database as history_db


def add_print_to_pdf_button():
    """
    Adiciona CSS para formatar a página para impressão e um botão
    discreto que aciona o diálogo de impressão (window.print()).
    """

    # 1. CSS (ATUALIZADO PARA USAR O "CANHÃO")
    print_css = """
    <style>
    @media print {
        /* Esconde elementos da UI */
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stHeader"] { display: none; }
        .no-print { display: none !important; }
        
        /* Otimiza o layout */
        [data-testid="stAppViewContainer"] { padding-top: 0; }
        
        /* --- INÍCIO DA CORREÇÃO --- */
        
        /* 1. Força o fundo para branco */
        body, [data-testid="stAppViewContainer"] {
            background: #ffffff !important;
        }

        /* 2. O "Canhão": Força TODO o texto (títulos, métricas,
           texto verde/vermelho, etc.) a ser PRETO. */
        * {
            color: #000000 !important;
        }
        
        /* --- FIM DA CORREÇÃO --- */
    }
    </style>
    """
    st.markdown(print_css, unsafe_allow_html=True)  #

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
    html(button_html, height=50)  #


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
        conn = sqlite3.connect(db_path, check_same_thread=False)  #
        conn.text_factory = str  #
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
    )  #

    if st.button("Calcular Resumo de Métricas"):  #
        with st.spinner("Calculando métricas..."):  #
            try:

                cursor = conn.cursor()  #
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
                )  #
                rows = cursor.fetchall()  #

                if not rows:  #
                    st.warning("Nenhuma avaliação encontrada no banco de dados.")
                    return

                st.success(f"Métricas calculadas para {len(rows)} tipo(s) de busca:")  #

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
                st.dataframe(data, use_container_width=True)  #

                st.markdown("---")  #
                st.header("Interpretação")  #
                st.markdown(
                    """
                    - **Hit Rate (Taxa de Acerto):** A porcentagem de vezes que *pelo menos um* chunk correto foi retornado. (Maior é melhor)
                    - **MRR (Mean Reciprocal Rank):** A média da "pontuação de ranking" do *primeiro* chunk correto. (Maior é melhor, 1.0 é perfeito)
                    - **Precisão@K Média:** A proporção média de chunks corretos por rodada (ex: 0.66 = 2 de 3 chunks estavam certos). Mede a "pureza" do resultado. (Maior é melhor)
                    """
                )  #

            except Exception as e:
                st.error(f"Erro ao calcular métricas: {e}")  #


def run_list_evaluations(conn):
    """Modo 2: Listar Avaliações Detalhadas"""
    st.subheader("Modo 2: Listar Avaliações Detalhadas")  #
    st.info(
        "Exibe cada rodada de validação e os chunks que foram marcados como corretos."
    )  #

    if st.button("Carregar Todas as Avaliações"):  #
        with st.spinner("Consultando avaliações..."):  #
            try:
                cursor = conn.cursor()  #

                # Query para buscar todas as rodadas
                cursor.execute(
                    """
                    SELECT id, timestamp, query, search_type, 
                           hit_rate_eval, mrr_eval, precision_at_k_eval
                    FROM validation_runs
                    ORDER BY timestamp DESC
                    """
                )  #
                runs = cursor.fetchall()  #

                if not runs:  #
                    st.warning("Nenhuma avaliação (rodada) encontrada.")
                    return

                # --- REQUISITO 1: Manter o total ---
                st.success(f"Total de rodadas de avaliação: {len(runs)}")  #

                # --- REQUISITO 2: Tabela de Resumo por Tipo ---
                cursor.execute(
                    """
                    SELECT search_type, COUNT(*) as total_runs
                    FROM validation_runs
                    GROUP BY search_type
                    """
                )  #
                summary_rows = cursor.fetchall()  #

                if summary_rows:  #
                    summary_data = [
                        {
                            "TIPO DE BUSCA": row[0],
                            "TOTAL DE AVALIAÇÕES": row[1],
                        }
                        for row in summary_rows
                    ]  #
                    st.markdown("**Total de Avaliações por Tipo:**")  #
                    st.dataframe(summary_data, use_container_width=True)  #

                st.divider()  #
                st.markdown("### Detalhamento das Rodadas")  #

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
                    run_id = int(run_id)  #
                    query = str(query)  #
                    s_type = str(s_type)  #
                    hr = int(hr)  #
                    mrr = float(mrr)  #
                    p_at_k = float(p_at_k)  #

                    hr_text = "✅ Sucesso" if hr == 1 else "❌ Falha"  #

                    with st.container(border=True):  #
                        # Linha de ID (mantida)
                        st.markdown(
                            f"**ID da Rodada: {run_id}** | {ts} | **Tipo: {s_type}**"
                        )  #

                        # --- REQUISITO 3: Destaque da Query ---
                        st.markdown("**Query:**")  #
                        st.markdown(f"> *{query}*")  # Usando blockquote e itálico

                        # --- REQUISITO 4: Destaque das Métricas ---
                        st.markdown("**Métricas da Rodada:**")  #
                        col1, col2, col3 = st.columns(3)  #
                        col1.metric(
                            label="Taxa de Acerto (Hit Rate)",
                            value=hr_text,
                            help="Indica se pelo menos um chunk relevante foi encontrado nesta rodada.",
                        )  #
                        col2.metric(label="MRR (Pontuação)", value=f"{mrr:.4f}")  #
                        col3.metric(label="Precisão@K", value=f"{p_at_k:.4f}")  #

                        st.markdown("**Chunks Retornados:**")  #

                        # Busca os chunks para esta rodada
                        cursor.execute(chunk_query, (run_id,))  #
                        chunks = cursor.fetchall()  #

                        for chunk in chunks:  #
                            (rank, content, source, page, score, is_correct) = chunk  #

                            rank = int(rank)  #
                            content = str(content)  #
                            source = str(source)  #
                            score = float(
                                score
                            )  # O diagnóstico provou que isso é um float
                            is_correct = int(is_correct)  #

                            page_str = str(page) if page is not None else "N/A"  #

                            # --- REQUISITO 5: Destaque do "Correto" ---
                            correct_text = "SIM 👍" if is_correct == 1 else "NÃO 👎"  #
                            correct_color = "green" if is_correct == 1 else "red"  #

                            st.markdown(
                                f"  **{rank}.** <font color='{correct_color}'>**(Correto: {correct_text})**</font> | [Score: {score:.4f}] - *{source}, p.{page}*",
                                unsafe_allow_html=True,
                            )  #
                            st.text(f"     {content[:150]}...")  #

            except Exception as e:
                st.error(f"Erro ao listar avaliações: {e}")  #


# --- FIM DA FUNÇÃO ATUALIZADA ---


def run_export_xml(conn):
    """Modo 3: Exportar Avaliações para XML"""
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


# --- FUNÇÃO DE IMPORTAÇÃO ATUALIZADA ---


def _safe_get_text(element, tag, default=None):
    """Tenta encontrar um sub-elemento e obter seu texto, retornando um padrão se falhar."""
    found = element.find(tag)  #
    if found is not None and found.text is not None:  #
        return found.text
    return default


def run_import_xml(conn):
    """Modo 4: Importar Avaliações de um arquivo XML"""
    st.subheader("Modo 4: Importar Avaliações (XML)")  #
    st.info(
        "Faça o upload de um arquivo 'avaliacoes_exportadas.xml' "
        "para adicionar os dados ao banco de dados atual."
    )  #
    st.warning(
        "O sistema irá verificar o 'timestamp' e ignorar "
        "automaticamente qualquer registro que já exista no banco."
    )

    uploaded_file = st.file_uploader(
        "Selecione o arquivo 'avaliacoes_exportadas.xml'", type=["xml"]
    )  #

    if uploaded_file is not None:
        if st.button("Iniciar Importação"):  #

            # --- INÍCIO DA ALTERAÇÃO ---
            # Contadores para o resumo
            runs_imported = 0
            runs_skipped = 0
            chunks_imported = 0
            total_runs_in_xml = 0
            file_name = uploaded_file.name
            # --- FIM DA ALTERAÇÃO ---

            try:
                # Parse o XML
                tree = ET.parse(uploaded_file)  #
                root = tree.getroot()  #

                cursor = conn.cursor()  #

                # Inicia a transação
                cursor.execute("BEGIN")  #

                all_runs_in_xml = root.findall("validation_run")  #
                total_runs_in_xml = len(all_runs_in_xml)

                # Itera sobre cada rodada de validação no XML
                for run in all_runs_in_xml:

                    # 1. Verificar se o timestamp já existe
                    run_timestamp = _safe_get_text(run, "timestamp")

                    if not run_timestamp:
                        # Se não houver timestamp no XML, não podemos
                        # verificar duplicidade, melhor pular.
                        runs_skipped += 1
                        continue

                    cursor.execute(
                        "SELECT 1 FROM validation_runs WHERE timestamp = ?",
                        (run_timestamp,),
                    )
                    exists = cursor.fetchone()

                    if exists:
                        # Timestamp encontrado, registro é duplicado.
                        runs_skipped += 1
                        continue

                    # --- Se não existe, importa ---
                    runs_imported += 1

                    # 2. Inserir na tabela 'validation_runs'
                    # Usamos o timestamp original do XML
                    query = _safe_get_text(run, "query", "")  #
                    search_type = _safe_get_text(run, "search_type", "unknown")  #
                    # Converte para os tipos corretos
                    hr_eval = float(_safe_get_text(run, "hit_rate_eval", 0.0))  #
                    mrr_eval = float(_safe_get_text(run, "mrr_eval", 0.0))  #
                    p_at_k_eval = float(
                        _safe_get_text(run, "precision_at_k_eval", 0.0)
                    )  #

                    cursor.execute(
                        """
                        INSERT INTO validation_runs 
                        (timestamp, query, search_type, hit_rate_eval, mrr_eval, precision_at_k_eval)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_timestamp,
                            query,
                            search_type,
                            hr_eval,
                            mrr_eval,
                            p_at_k_eval,
                        ),
                    )

                    # Obtém o ID da rodada que acabamos de inserir
                    new_run_id = cursor.lastrowid  #

                    # 3. Inserir os chunks associados
                    chunks_element = run.find("retrieved_chunks")  #
                    if chunks_element is not None:
                        for chunk in chunks_element.findall("chunk"):  #
                            rank = int(_safe_get_text(chunk, "rank", 0))  #
                            content = _safe_get_text(chunk, "chunk_content", "")  #
                            source = _safe_get_text(chunk, "source", "N/A")  #
                            page = _safe_get_text(chunk, "page")  #
                            score = float(_safe_get_text(chunk, "score", 0.0))  #
                            is_correct = int(
                                _safe_get_text(chunk, "is_correct_eval", 0)
                            )  #

                            # Trata 'page' que pode ser 'None' (string) ou numérico
                            page_int = None  #
                            if page is not None and page.lower() != "none":  #
                                try:
                                    page_int = int(float(page))  #
                                except (ValueError, TypeError):
                                    page_int = None  # Deixa nulo se a conversão falhar

                            cursor.execute(
                                """
                                INSERT INTO validation_retrieved_chunks
                                (run_id, rank, chunk_content, source, page, score, is_correct_eval)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    new_run_id,
                                    rank,
                                    content,
                                    source,
                                    page_int,
                                    score,
                                    is_correct,
                                ),
                            )  #
                            chunks_imported += 1

                # Completa a transação
                conn.commit()  #

                # --- INÍCIO DA ALTERAÇÃO (Resumo) ---
                st.success("Importação concluída!")
                st.markdown(f"**Resumo da Importação (Arquivo: `{file_name}`)**")

                # Exibe o total do arquivo
                st.metric(
                    label="Total de Validações no Arquivo", value=total_runs_in_xml
                )

                # Colunas para importados vs. ignorados
                col1, col2 = st.columns(2)
                col1.metric(label="Rodadas Importadas (Novas)", value=runs_imported)
                col2.metric(label="Rodadas Ignoradas (Duplicadas)", value=runs_skipped)

                # Informação adicional sobre chunks
                st.info(
                    f"Total de {chunks_imported} chunks associados foram importados."
                )
                # --- FIM DA ALTERAÇÃO ---

            except Exception as e:
                # Desfaz em caso de erro
                conn.rollback()  #
                st.error(f"Erro durante a importação: {e}")
                st.error("Nenhum dado foi importado.")


# --- FIM DA FUNÇÃO ATUALIZADA ---


def run_shutdown():
    """Modo 5: Encerrar"""  # <-- Título do docstring precisa ser atualizado
    st.subheader("Modo 5: Encerrar Servidor")  # <-- Label atualizado para 5
    st.warning("Clicar neste botão encerrará este servidor Streamlit.")  #

    if st.button("Encerrar Aplicação"):  #
        st.success("Encerrando servidor...")  #
        print("Comando de encerramento recebido da UI.")  #
        os._exit(0)  # Força a parada do processo Python


def main():
    st.set_page_config(page_title="Auditoria de Avaliação", layout="wide")  #
    st.title("Ferramenta de Auditoria de Métricas (HR, MRR & Precisão@K)")  #
    st.caption(
        "Esta interface consulta as tabelas 'validation_runs' do 'chat_solution.db'."
    )  #

    conn = connect_to_db()  #

    st.sidebar.title("Opções de Auditoria")

    # Adiciona o botão de imprimir no topo da barra lateral
    st.sidebar.markdown("---")
    add_print_to_pdf_button()
    st.sidebar.markdown("---")

    # --- Menu de Opções ATUALIZADO ---
    opcoes = [
        "1. Resumo das Métricas (HR, MRR & P@K)",
        "2. Listar Avaliações Detalhadas",
        "3. Exportar Avaliações (XML)",
        "4. Importar Avaliações (XML)",  # <-- NOVO
        "5. Encerrar Servidor",  # <-- Renumerado
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

    # --- Roteamento ATUALIZADO ---
    elif modo == opcoes[3]:  #
        run_import_xml(conn)  # <-- NOVO
    elif modo == opcoes[4]:  #
        run_shutdown()  #
    # --- FIM DAS ALTERAÇÕES ---


if __name__ == "__main__":
    main()  #
