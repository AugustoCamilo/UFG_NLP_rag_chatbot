# validate_vector_db.py
"""
Módulo de Frontend para Avaliação Manual do Retriever (Entrada de Dados).

Esta aplicação Streamlit é a principal ferramenta do avaliador humano para
testar a qualidade do sistema de recuperação (Retrieval) e *criar* os
dados de "verdade de campo" (ground truth).

Enquanto o `validate_evaluation.py` é o *dashboard de
análise* (que lê os dados), este script é a *ferramenta de
entrada* (que escreve os dados).

Ele se conecta ao VectorDB (Chroma) e ao banco de
avaliação (SQLite).

---
### Funcionalidades Principais (Modos)
---

A aplicação é dividida em cinco modos principais:

1.  **Testar Busca (SÓ Vetorial):**
    * Executa `run_search_test_no_rerank`.
    * Testa a performance do "Recall" puro, chamando
        `retriever.retrieve_context_vector_search_only`
        para buscar os K_FINAL chunks.

2.  **Testar Busca (COM Re-Ranking):**
    * Executa `run_search_test`.
    * Testa a performance do "Recall + Precisão", chamando
        `retriever.retrieve_context_with_scores` para
        buscar K_RAW chunks, re-ranquear, e exibir
        os K_FINAL melhores.

3.  **Listar Todos os Chunks:**
    * Executa `run_list_all`.
    * Uma ferramenta de utilidade para inspecionar o conteúdo
        bruto do banco de vetores ChromaDB (via `retriever.get_all_chunks`).

4.  **Exportar Chunks para XML:**
    * Executa `run_export_xml`.
    * Exporta o conteúdo bruto do ChromaDB.

5.  **Encerrar Servidor:**
    * Executa `run_shutdown` para parar o servidor.

---
### Fluxo de Avaliação (Modos 1 e 2)
---

O fluxo principal de avaliação é o coração deste script:

1.  **Busca:** O usuário insere uma query e executa uma busca (vetorial ou
    re-ranking).
2.  **Exibição (`display_search_results`):** A interface
    exibe os chunks encontrados e apresenta um formulário de avaliação.
3.  **Coleta de Métricas (Formulário):**
    * **Checkboxes (Relevância):** O avaliador marca *todos* os chunks
        corretos. (Usado para calcular Hit Rate e Precisão@K).
    * **Radio Buttons (MRR):** O avaliador marca o *melhor* chunk
        (o primeiro mais relevante).
4.  **Salvamento (`save_evaluation_to_db`):**
    * Quando o formulário é enviado, esta função calcula as três
        métricas (Hit Rate, MRR, Precisão@K).
    * Ela então salva a query e as métricas na tabela `validation_runs`.
    * Salva cada chunk individual, seu score, e se foi marcado
        como correto (`is_correct_eval`) na tabela
        `validation_retrieved_chunks`.
    * *Nota:* Esta função converte os scores (`numpy.float`) para
        `float` nativo do Python antes de salvar, para evitar
        corrupção de dados (BLOBs) no SQLite.
"""


import streamlit as st
import os
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from streamlit.components.v1 import html
import config
import sqlite3


# Importa a classe centralizada que faz o trabalho pesado
from vector_retriever import VectorRetriever

# Importa o caminho do DB para salvar as avaliações
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


@st.cache_resource
def initialize_retriever():
    """Carrega o VectorRetriever e o armazena no cache."""
    st.write("Inicializando o VectorRetriever (Carregando modelos na 1ª execução)...")
    try:
        retriever = VectorRetriever()
        st.sidebar.success("Retriever carregado.")
        return retriever
    except FileNotFoundError as e:
        st.error(
            f"Erro: Banco de vetores não encontrado em '{e}'. "
            "Execute 'python ingest.py' primeiro."
        )
        st.stop()
    except Exception as e:
        st.error(f"Erro fatal ao carregar o VectorRetriever: {e}")
        st.stop()


# --- FUNÇÃO DE SALVAMENTO ---
def save_evaluation_to_db(query, search_type, results_map, hit_rate_evals, mrr_score):
    """
    Salva a consulta, os chunks e as avaliações (Hit Rate, MRR e Precisão@K)
    no banco.
    'hit_rate_evals' (dict): {1: True, 2: False, ...} - dos checkboxes
    'mrr_score' (float): A pontuação MRR já calculada
    """
    conn = None
    try:
        conn = sqlite3.connect(history_db.DB_PATH)  #
        cursor = conn.cursor()

        # 1. Calcular Métrica 1: Hit Rate (Binário, 1/0)
        hit_rate = 1 if any(hit_rate_evals.values()) else 0  #

        # 2. Calcular Métrica 2: MRR
        mrr = float(mrr_score)

        # --- INÍCIO DA ALTERAÇÃO ---
        # 3. Calcular Métrica 3: Precisão@K

        # K é o número total de resultados mostrados (ex: 3)
        k = len(results_map)

        # hit_count é a contagem de checkboxes marcados
        hit_count = sum(bool(v) for v in hit_rate_evals.values())

        # Precisão = (Chunks Corretos) / (Total de Chunks Mostrados)
        precision = (hit_count / k) if k > 0 else 0.0
        # Força para float nativo
        precision = float(precision)

        # 4. Inserir na tabela 'validation_runs'
        cursor.execute(
            """
            INSERT INTO validation_runs (
                query, search_type, 
                hit_rate_eval, mrr_eval, precision_at_k_eval
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                query,
                search_type,
                hit_rate,
                mrr,
                precision,
            ),  # <-- 'precision' adicionado
        )  #

        run_id = cursor.lastrowid  #

        # 5. Inserir cada chunk... (lógica inalterada)
        for rank, (doc, score) in results_map.items():
            is_correct = 1 if hit_rate_evals.get(rank, False) else 0
            # Garante que o score (que é numpy.float)
            # seja salvo como um float nativo do Python.
            score_float = float(score)

            cursor.execute(
                """
                INSERT INTO validation_retrieved_chunks 
                (run_id, rank, chunk_content, source, page, score, is_correct_eval)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    rank,
                    doc.page_content,
                    doc.metadata.get("source", "N/A"),
                    doc.metadata.get("page", None),
                    score_float,
                    is_correct,
                ),
            )  #

        conn.commit()  #
        st.success(f"Avaliação salva com sucesso! (ID da Rodada: {run_id})")  #

    except Exception as e:
        if conn:
            conn.rollback()  #
        st.error(f"Erro ao salvar avaliação no banco de dados: {e}")  #
    finally:
        if conn:
            conn.close()


# --- FUNÇÃO DE DISPLAY ATUALIZADA ---
def display_search_results(query, search_type, results_with_scores):
    """
    Exibe os resultados da busca E o formulário de avaliação
    com Checkboxes (Hit Rate) e Radio Buttons (MRR).
    """

    results_map = {
        i + 1: (doc, score) for i, (doc, score) in enumerate(results_with_scores)
    }

    if not results_map:
        st.warning("Nenhum resultado relevante encontrado.")
        return

    st.success(f"Exibindo os {len(results_map)} resultados:")

    # Exibe os resultados
    for rank, (doc, score) in results_map.items():
        source = doc.metadata.get("source", "N/A")
        page = doc.metadata.get("page", "N/A")
        score_label = (
            "Score de Relevância" if search_type == "reranked" else "Score de Distância"
        )

        with st.container(border=True):
            st.markdown(f"**Resultado {rank} ({score_label}: {score:.4f})**")
            st.caption(f"Fonte: {source} | Página: {page}")
            st.markdown(doc.page_content)

    st.divider()

    # --- Formulário de Avaliação  ---
    st.subheader("Avaliar Resultados")

    with st.form(key=f"eval_form_{search_type}"):

        # 1. Métrica 1: Hit Rate (Checkboxes)
        st.info(
            "Avaliação de Relevância (Hit Rate / Precisão@K): "
            "Marque TODOS os chunks que são relevantes."
        )
        evaluations_hit_rate = {}
        for rank in results_map.keys():
            evaluations_hit_rate[rank] = st.checkbox(
                f"Resultado {rank} está correto", key=f"check_{search_type}_{rank}"
            )

        st.divider()

        # 2. Métrica 2: MRR (Radio Buttons)
        st.info(
            "MRR (Mean Reciprocal Rank): Selecione a MELHOR resposta "
            "(a que melhor responde à pergunta)."
        )

        # Cria as opções para o Radio
        # Ex: ["Resultado 1 (MRR = 1)", "Resultado (MRR = 0.5)", "Resultado (MRR = 0.33)", "Nenhuma (MRR = 0)"]
        radio_options = []
        for rank in results_map.keys():
            mrr_score = 1.0 / rank
            # Adiciona a opção formatada
            radio_options.append(f"Resultado {rank} (MRR = {mrr_score:.2f})")

        radio_options.append("Nenhuma (MRR = 0)")

        selected_radio = st.radio(
            "Selecione o melhor resultado:",
            options=radio_options,
            key=f"radio_{search_type}",
            index=len(radio_options) - 1,  # Padrão é "Nenhuma"
        )

        submit_eval_button = st.form_submit_button(label="Salvar Avaliação")

    if submit_eval_button:

        # 1. Processar a seleção do Radio para obter o rank (1, 2, 3... ou 0)
        mrr_eval_rank = 0
        if selected_radio != "Nenhuma (MRR = 0)":
            # Extrai o número do texto "Resultado X"
            mrr_eval_rank = int(selected_radio.split(" ")[1])  #

        # 2. Calcular a pontuação MRR conforme a fórmula
        mrr_score = 0.0
        if mrr_eval_rank > 0:
            mrr_score = 1.0 / mrr_eval_rank

        # 3. Passar o 'mrr_score' (calculado) em vez do 'mrr_eval_rank' (bruto)
        save_evaluation_to_db(
            query,
            search_type,
            results_map,
            evaluations_hit_rate,
            mrr_score,  # Passando o score (0.0, 0.33, 0.5, 1)
        )

        # 1. Limpa o estado da sessão para "resetar" a UI
        if "results" in st.session_state:
            del st.session_state.results
        if "query" in st.session_state:
            del st.session_state.query
        if "search_type" in st.session_state:
            del st.session_state.search_type

        # Limpa os campos de texto (widgets)
        st.session_state.clear_inputs = True

        # 2. Força o Streamlit a rodar o script do início
        st.rerun()


def run_search_test_no_rerank(retriever: VectorRetriever):
    """Modo 1: Testar Busca Vetorial Apenas"""
    st.subheader("Modo 1: Testar Busca (SÓ Vetorial, sem Re-Ranking)")
    st.info(
        f"Testa o RECALL. Busca {config.SEARCH_K_FINAL} e exibe {config.SEARCH_K_FINAL}."
    )

    with st.form(key="search_form_no_rerank"):
        query = st.text_input(
            "Digite sua consulta (pergunta):", key="query_input_no_rerank"
        )
        submit_button = st.form_submit_button(label="Buscar")

    if submit_button and query:
        st.session_state.query = query
        st.session_state.search_type = "vector_only"

        with st.spinner("Etapa 1 (Recall) em progresso..."):
            top_k_results = retriever.retrieve_context_vector_search_only(query)
            st.session_state.results = top_k_results

    if "results" in st.session_state and st.session_state.search_type == "vector_only":
        display_search_results(
            st.session_state.query,
            st.session_state.search_type,
            st.session_state.results,
        )


def run_search_test(retriever: VectorRetriever):
    """Modo 2: Testar Busca com Re-Ranking"""
    st.subheader("Modo 2: Testar Busca (COM Re-Ranking)")
    st.info(
        f"Testa a PRECISÃO. Busca {config.SEARCH_K_RAW}, re-rankeia e exibe {config.SEARCH_K_FINAL}."
    )

    with st.form(key="search_form_rerank"):
        query = st.text_input(
            "Digite sua consulta (pergunta):", key="query_input_rerank"
        )
        submit_button = st.form_submit_button(label="Buscar")

    if submit_button and query:
        st.session_state.query = query
        st.session_state.search_type = "reranked"

        with st.spinner("Etapa 1 (Recall) e Etapa 2 (Re-Ranking) em progresso..."):
            top_k_results = retriever.retrieve_context_with_scores(query)
            st.session_state.results = top_k_results

    if "results" in st.session_state and st.session_state.search_type == "reranked":
        display_search_results(
            st.session_state.query,
            st.session_state.search_type,
            st.session_state.results,
        )


def run_list_all(retriever: VectorRetriever):
    """Modo 3: Listar Todos os Chunks"""
    st.subheader("Modo 3: Listar Todos os Chunks no Banco")
    if st.button("Clique para carregar e listar todos os chunks"):
        with st.spinner("Buscando todos os chunks..."):
            data = retriever.get_all_chunks()
            documents = data.get("documents")
            metadatas = data.get("metadatas")

        if not documents:
            st.warning("O banco de dados está vazio. Nenhum chunk encontrado.")
        else:
            st.success(f"Total de chunks encontrados no banco: {len(documents)}")
            for i in range(len(documents)):
                doc_text = documents[i]
                source = metadatas[i].get("source", "N/A")
                with st.container(border=True):
                    st.markdown(f"**Chunk {i+1}**")
                    st.caption(f"Fonte: {source}")
                    st.text(f"{doc_text[:350]}...")


def run_export_xml(retriever: VectorRetriever):
    """Modo 4: Exportar Chunks para XML"""
    st.subheader("Modo 4: Exportar Chunks para XML")
    st.info("O arquivo será salvo na pasta raiz do projeto.")

    if st.button("Gerar Arquivo 'chunks_exportados.xml'"):
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        output_filename = "chunks_exportados.xml"
        output_path = os.path.join(SCRIPT_DIR, output_filename)

        with st.spinner("Exportando chunks para XML..."):
            data = retriever.get_all_chunks()
            documents = data.get("documents")
            metadatas = data.get("metadatas")

            if not documents:
                st.error("O banco de dados está vazio. Nada para exportar.")
                return

            total_chunks = len(documents)
            root = ET.Element("dados_chunks")
            now = datetime.now()
            timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
            comment_text = f" Exportação gerada em: {timestamp_str}. Total de chunks: {total_chunks} "
            comment = ET.Comment(comment_text)
            root.insert(0, comment)

            for i in range(len(documents)):
                doc_text = documents[i]
                meta = metadatas[i]
                item = ET.SubElement(root, "item")
                chunk_id_el = ET.SubElement(item, "chunk_id")
                chunk_id_el.text = str(i + 1)
                conteudo_el = ET.SubElement(item, "conteudo")
                conteudo_el.text = doc_text
                metadatos_el = ET.SubElement(item, "metadados")
                for key, value in meta.items():
                    meta_key_el = ET.SubElement(metadatos_el, key.replace(" ", "_"))  # type: ignore
                    meta_key_el.text = str(value)
            try:
                xml_string = ET.tostring(root, "utf-8")
                parsed_string = minidom.parseString(xml_string)
                pretty_xml = parsed_string.toprettyxml(indent="  ", encoding="utf-8")
                with open(output_path, "wb") as f:
                    f.write(pretty_xml)
                st.success(f"Sucesso! {total_chunks} chunks exportados para:")
                st.code(output_path, language="bash")
            except Exception as e:
                st.error(f"Erro ao salvar o arquivo XML: {e}")


def run_shutdown():
    """Modo 5: Encerrar"""
    st.subheader("Modo 5: Encerrar Servidor")
    st.warning("Clicar neste botão encerrará este servidor Streamlit.")
    if st.button("Encerrar Aplicação"):
        st.success("Encerrando servidor...")
        print("Comando de encerramento recebido da UI.")
        os._exit(0)


def main():
    st.set_page_config(page_title="Validação do VectorDB", layout="wide")

    # Verifica se o sinalizador de limpeza foi ativado no 'rerun' anterior
    if st.session_state.get("clear_inputs", False):
        st.session_state.query_input_no_rerank = ""
        st.session_state.query_input_rerank = ""
        st.session_state.clear_inputs = False  # Reseta o sinalizador

    st.title("Ferramenta de Validação do Banco de Vetores (ChromaDB)")
    st.caption(
        "Interface de auditoria para o VectorDB (baseado em 'vector_retriever.py' e 'ingest.py')"
    )

    retriever = initialize_retriever()

    st.sidebar.title("Opções de Validação")

    st.sidebar.markdown("---")
    add_print_to_pdf_button()
    st.sidebar.markdown("---")

    opcoes = [
        "1. Testar Busca (SÓ Vetorial)",
        "2. Testar Busca (COM Re-Ranking)",
        "3. Listar Todos os Chunks",
        "4. Exportar Chunks para XML",
        "5. Encerrar Servidor",
    ]
    modo = st.sidebar.radio(
        "Selecione uma operação:", opcoes, label_visibility="collapsed"
    )

    # Limpa o estado da sessão se o modo for alterado
    if "current_mode" not in st.session_state or st.session_state.current_mode != modo:
        st.session_state.current_mode = modo
        if "results" in st.session_state:
            del st.session_state.results
        if "query" in st.session_state:
            del st.session_state.query
        if "search_type" in st.session_state:
            del st.session_state.search_type

    if modo == opcoes[0]:
        run_search_test_no_rerank(retriever)
    elif modo == opcoes[1]:
        run_search_test(retriever)
    elif modo == opcoes[2]:
        run_list_all(retriever)
    elif modo == opcoes[3]:
        run_export_xml(retriever)
    elif modo == opcoes[4]:
        run_shutdown()


if __name__ == "__main__":
    main()
