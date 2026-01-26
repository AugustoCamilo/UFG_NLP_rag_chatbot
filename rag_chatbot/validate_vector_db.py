# validate_vector_db.py
"""
Módulo de Frontend para Avaliação Manual do Retriever (Entrada de Dados).

Esta aplicação Streamlit é a principal ferramenta do avaliador humano para
testar a qualidade do sistema de recuperação (Retrieval) e criar os
dados de "verdade de campo" (ground truth).
"""

import streamlit as st
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from sqlmodel import Session, create_engine

# --- Imports do Projeto ---
from settings import settings
from ui_utils import add_print_to_pdf_button
from vector_retriever import VectorRetriever

# --- Importação da Camada de Dados (SQLModel) ---
from database import ValidationRun, ValidationRetrievedChunk

# Configuração do Engine Síncrono para o Streamlit
engine = create_engine(settings.SYNC_DATABASE_URL)


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


def _safe_get_text(element, tag, default=None):
    """Helper para ler XML de forma segura (Padrão validate_evaluation)."""
    found = element.find(tag)
    if found is not None and found.text is not None:
        return found.text
    return default


# --- FUNÇÃO DE SALVAMENTO ---
def save_evaluation_to_db(query, search_type, results_map, hit_rate_evals, mrr_score):
    """Salva a consulta, os chunks e as avaliações no banco usando SQLModel."""
    try:
        with Session(engine) as session:
            # 1. Calcular Métricas
            hit_rate = 1 if any(hit_rate_evals.values()) else 0
            mrr = float(mrr_score)
            k = len(results_map)
            hit_count = sum(bool(v) for v in hit_rate_evals.values())
            precision = (hit_count / k) if k > 0 else 0.0
            precision = float(precision)

            # 2. Criar e Salvar a Rodada
            run_entry = ValidationRun(
                query=query,
                search_type=search_type,
                hit_rate_eval=hit_rate,
                mrr_eval=mrr,
                precision_at_k_eval=precision,
                timestamp=datetime.now(),
            )
            session.add(run_entry)
            session.commit()
            session.refresh(run_entry)

            # 3. Criar e Salvar os Chunks
            for rank, (doc, score) in results_map.items():
                is_correct = 1 if hit_rate_evals.get(rank, False) else 0
                score_float = float(score)
                page_val = doc.metadata.get("page", None)
                if page_val is not None:
                    try:
                        page_val = int(page_val)
                    except:
                        page_val = None

                chunk_entry = ValidationRetrievedChunk(
                    run_id=run_entry.id,
                    rank=rank,
                    chunk_content=doc.page_content,
                    source=doc.metadata.get("source", "N/A"),
                    page=page_val,
                    score=score_float,
                    is_correct_eval=is_correct,
                )
                session.add(chunk_entry)

            session.commit()
            st.success(f"Avaliação salva com sucesso! (ID da Rodada: {run_entry.id})")

    except Exception as e:
        st.error(f"Erro ao salvar avaliação no banco de dados: {e}")


# --- FUNÇÃO DE DISPLAY ---
def display_search_results(query, search_type, results_with_scores):
    """Exibe os resultados da busca E o formulário de avaliação."""
    results_map = {
        i + 1: (doc, score) for i, (doc, score) in enumerate(results_with_scores)
    }

    if not results_map:
        st.warning("Nenhum resultado relevante encontrado.")
        return

    st.success(f"Exibindo os {len(results_map)} resultados:")

    for rank, (doc, score) in results_map.items():
        source = doc.metadata.get("source", "N/A")
        page = doc.metadata.get("page", "N/A")
        score_label = (
            "Score de Relevância"
            if search_type == "reranked_USER"
            else "Score de Distância"
        )

        with st.container(border=True):
            st.markdown(f"**Resultado {rank} ({score_label}: {score:.4f})**")
            st.caption(f"Fonte: {source} | Página: {page}")
            st.markdown(doc.page_content)

    st.divider()
    st.subheader("Avaliar Resultados")

    with st.form(key=f"eval_form_{search_type}"):
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
        st.info(
            "MRR (Mean Reciprocal Rank): Selecione a MELHOR resposta "
            "(a que melhor responde à pergunta)."
        )

        radio_options = []
        for rank in results_map.keys():
            mrr_score = 1.0 / rank
            radio_options.append(f"Resultado {rank} (MRR = {mrr_score:.2f})")
        radio_options.append("Nenhuma (MRR = 0)")

        selected_radio = st.radio(
            "Selecione o melhor resultado:",
            options=radio_options,
            key=f"radio_{search_type}",
            index=len(radio_options) - 1,
        )

        submit_eval_button = st.form_submit_button(label="Salvar Avaliação")

    if submit_eval_button:
        mrr_eval_rank = 0
        if selected_radio != "Nenhuma (MRR = 0)":
            mrr_eval_rank = int(selected_radio.split(" ")[1])

        mrr_score = 0.0
        if mrr_eval_rank > 0:
            mrr_score = 1.0 / mrr_eval_rank

        save_evaluation_to_db(
            query,
            search_type,
            results_map,
            evaluations_hit_rate,
            mrr_score,
        )

        if "results" in st.session_state:
            del st.session_state.results
        if "query" in st.session_state:
            del st.session_state.query
        if "search_type" in st.session_state:
            del st.session_state.search_type

        st.session_state.clear_inputs = True
        st.rerun()


def run_search_test_no_rerank(retriever: VectorRetriever):
    """Modo 1: Testar Busca Vetorial Apenas"""
    st.subheader("Modo 1: Testar Busca (SÓ Vetorial, sem Re-Ranking)")
    st.info(
        f"Testa o RECALL. Busca {settings.SEARCH_K_FINAL} e exibe {settings.SEARCH_K_FINAL}."
    )

    with st.form(key="search_form_no_rerank"):
        query = st.text_input(
            "Digite sua consulta (pergunta):", key="query_input_no_rerank"
        )
        submit_button = st.form_submit_button(label="Buscar")

    if submit_button and query:
        st.session_state.query = query
        st.session_state.search_type = "vector_only_USER"

        with st.spinner("Etapa 1 (Recall) em progresso..."):
            top_k_results = retriever.retrieve_context_vector_search_only(query)
            st.session_state.results = top_k_results

    if (
        "results" in st.session_state
        and st.session_state.search_type == "vector_only_USER"
    ):
        display_search_results(
            st.session_state.query,
            st.session_state.search_type,
            st.session_state.results,
        )


def run_search_test(retriever: VectorRetriever):
    """Modo 2: Testar Busca com Re-Ranking"""
    st.subheader("Modo 2: Testar Busca (COM Re-Ranking)")
    st.info(
        f"Testa a PRECISÃO. Busca {settings.SEARCH_K_RAW}, re-rankeia e exibe {settings.SEARCH_K_FINAL}."
    )

    with st.form(key="search_form_rerank"):
        query = st.text_input(
            "Digite sua consulta (pergunta):", key="query_input_rerank"
        )
        submit_button = st.form_submit_button(label="Buscar")

    if submit_button and query:
        st.session_state.query = query
        st.session_state.search_type = "reranked_USER"

        with st.spinner("Etapa 1 (Recall) e Etapa 2 (Re-Ranking) em progresso..."):
            top_k_results = retriever.retrieve_context_with_scores(query)
            st.session_state.results = top_k_results

    if (
        "results" in st.session_state
        and st.session_state.search_type == "reranked_USER"
    ):
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

                # ID apenas para referência no XML
                chunk_id_el = ET.SubElement(item, "chunk_id")
                chunk_id_el.text = str(i + 1)

                conteudo_el = ET.SubElement(item, "conteudo")
                conteudo_el.text = doc_text

                metadatos_el = ET.SubElement(item, "metadados")
                for key, value in meta.items():
                    if key:  # evitar chaves vazias
                        clean_key = key.replace(" ", "_")
                        meta_key_el = ET.SubElement(metadatos_el, clean_key)
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


def run_import_xml(retriever: VectorRetriever):
    """Modo 5: Importar Chunks (XML)"""
    st.subheader("Modo 5: Importar Chunks de XML (Adicionar à Base)")
    st.info(
        "Importa chunks do XML para o VectorDB. Ignora conteúdos que já existem no banco."
    )

    uploaded_file = st.file_uploader(
        "Selecione o arquivo XML (formato chunks_exportados.xml)", type=["xml"]
    )

    if uploaded_file and st.button("Iniciar Importação"):
        imported_count = 0
        skipped_count = 0

        try:
            # 1. Carregar base atual para verificação de duplicidade (Performance)
            with st.spinner("Verificando duplicidade na base atual..."):
                existing_data = retriever.get_all_chunks()
                # Set para busca O(1)
                existing_contents = set(existing_data.get("documents", []))

            # 2. Parse do XML
            tree = ET.parse(uploaded_file)
            root = tree.getroot()
            items = root.findall("item")

            new_texts = []
            new_metadatas = []

            # 3. Processamento dos itens
            for item in items:
                content = _safe_get_text(item, "conteudo")

                if not content:
                    continue

                # Verificação de Duplicidade
                if content in existing_contents:
                    skipped_count += 1
                    continue

                # Extração de Metadados
                meta_dict = {}
                metadados_node = item.find("metadados")
                if metadados_node is not None:
                    for meta_child in metadados_node:
                        if meta_child.tag and meta_child.text:
                            meta_dict[meta_child.tag] = meta_child.text

                # Tratamento de tipos específicos (opcional, mas recomendado)
                if "page" in meta_dict and meta_dict["page"] != "None":
                    try:
                        meta_dict["page"] = int(meta_dict["page"])
                    except:
                        pass

                new_texts.append(content)
                new_metadatas.append(meta_dict)

            # 4. Inserção em Lote no ChromaDB
            if new_texts:
                with st.spinner(
                    f"Adicionando {len(new_texts)} novos chunks ao banco..."
                ):
                    retriever.vectordb.add_texts(
                        texts=new_texts, metadatas=new_metadatas
                    )
                imported_count = len(new_texts)

            st.success("Processo concluído!")
            col1, col2 = st.columns(2)
            col1.metric("Importados (Novos)", imported_count)
            col2.metric("Ignorados (Duplicados)", skipped_count)

        except Exception as e:
            st.error(f"Erro durante a importação: {e}")


def run_shutdown():
    """Modo 6: Sair"""
    st.subheader("Modo 6: Sair")
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
        st.session_state.clear_inputs = False

    st.title("Ferramenta de Validação do Banco de Vetores (Chunks)")
    st.caption(
        "Interface de auditoria para o VectorDB (baseado em 'vector_retriever.py' e 'ingest.py')"
    )

    retriever = initialize_retriever()

    # --- DEFINIÇÃO DOS BLOCOS DE MENU ---
    # Grupo 1: Ferramentas
    tools_options = [
        "1. Testar Busca (SÓ Vetorial)",
        "2. Testar Busca (COM Re-Ranking)",
    ]

    # Grupo 2: Relatórios
    reports_options = [
        "3. Listar Todos os Chunks",
        "4. Exportar Chunks para XML",
        "5. Importar Chunks (XML)",
        "6. Sair",
    ]

    # --- GESTÃO DE ESTADO DO MENU (MUTUAMENTE EXCLUSIVO) ---
    if "menu_selection" not in st.session_state:
        st.session_state.menu_selection = tools_options[0]  # Default

    # Callbacks para garantir que apenas um radio tenha seleção ativa visualmente
    def update_from_tools():
        st.session_state.menu_selection = st.session_state.radio_tools

    def update_from_reports():
        st.session_state.menu_selection = st.session_state.radio_reports

    # --- RENDERIZAÇÃO DA SIDEBAR ---
    st.sidebar.title("Ferramentas de validação")

    # Define o índice do Radio 1 com base na seleção global
    tools_index = None
    if st.session_state.menu_selection in tools_options:
        tools_index = tools_options.index(st.session_state.menu_selection)

    st.sidebar.radio(
        "Ferramentas:",
        tools_options,
        index=tools_index,
        key="radio_tools",
        label_visibility="collapsed",
        on_change=update_from_tools,
    )

    st.sidebar.markdown("---")
    st.sidebar.title("Relatórios")

    # Define o índice do Radio 2 com base na seleção global
    reports_index = None
    if st.session_state.menu_selection in reports_options:
        reports_index = reports_options.index(st.session_state.menu_selection)

    st.sidebar.radio(
        "Relatórios:",
        reports_options,
        index=reports_index,
        key="radio_reports",
        label_visibility="collapsed",
        on_change=update_from_reports,
    )

    add_print_to_pdf_button()
    st.sidebar.markdown("---")

    # --- ROTEAMENTO DA SELEÇÃO ---
    modo = st.session_state.menu_selection

    # Limpa o estado da busca se mudar de funcionalidade
    if "current_mode" not in st.session_state or st.session_state.current_mode != modo:
        st.session_state.current_mode = modo
        if "results" in st.session_state:
            del st.session_state.results
        if "query" in st.session_state:
            del st.session_state.query
        if "search_type" in st.session_state:
            del st.session_state.search_type

    # Execução baseada na string selecionada
    if modo == tools_options[0]:
        run_search_test_no_rerank(retriever)
    elif modo == tools_options[1]:
        run_search_test(retriever)
    elif modo == reports_options[0]:
        run_list_all(retriever)
    elif modo == reports_options[1]:
        run_export_xml(retriever)
    elif modo == reports_options[2]:
        run_import_xml(retriever)
    elif modo == reports_options[3]:
        run_shutdown()


if __name__ == "__main__":
    main()
