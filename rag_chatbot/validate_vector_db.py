# validate_vector_db.py
import streamlit as st
import os
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import config  # Import necessário

# Importa a classe centralizada que faz o trabalho pesado
from vector_retriever import VectorRetriever


@st.cache_resource
def initialize_retriever():
    """
    Carrega o VectorRetriever (que inicializa os modelos de embedding e
    re-ranking) e o armazena no cache do Streamlit.
    """
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


def run_search_test(retriever: VectorRetriever):
    """Lógica da UI para o Modo 1: Testar Busca"""
    st.subheader("Modo 1: Testar Busca com Re-Ranking")
    st.info(
        "Esta tela executa a mesma lógica do chatbot: "
        f"1) Busca vetorial (Recall) de {config.SEARCH_K_RAW} chunks, "
        f"2) Re-Ranking (Precision) para os {config.SEARCH_K_FINAL} melhores."
    )

    with st.form(key="search_form"):
        query = st.text_input("Digite sua consulta (pergunta):", key="query_input")
        submit_button = st.form_submit_button(label="Buscar")

    if submit_button and query:
        st.write(f"Executando busca para: '{query}'")
        with st.spinner("Etapa 1 (Recall) e Etapa 2 (Re-Ranking) em progresso..."):
            # Usa o método do retriever que retorna os scores
            top_k_results = retriever.retrieve_context_with_scores(query)

        if not top_k_results:
            st.warning("Nenhum resultado relevante encontrado.")
        else:
            st.success(f"Exibindo os {len(top_k_results)} resultados MAIS RELEVANTES:")

            # --- COMENTÁRIO ATUALIZADO ---
            # Exibe os resultados da busca
            for i, (doc, rerank_score) in enumerate(top_k_results):
                source = doc.metadata.get("source", "N/A")
                page = doc.metadata.get("page", "N/A")
                with st.container(border=True):
                    st.markdown(
                        f"**Resultado {i+1} (Score de Relevância: {rerank_score:.4f})**"
                    )
                    st.caption(f"Fonte: {source} | Página: {page}")
                    st.markdown(doc.page_content)


def run_list_all(retriever: VectorRetriever):
    """Lógica da UI para o Modo 2: Listar Todos os Chunks"""
    st.subheader("Modo 2: Listar Todos os Chunks no Banco")
    if st.button("Clique para carregar e listar todos os chunks"):
        with st.spinner("Buscando todos os chunks..."):
            # Usa o método do retriever para obter os dados
            data = retriever.get_all_chunks()
            documents = data.get("documents")
            metadatas = data.get("metadatas")

        if not documents:
            st.warning("O banco de dados está vazio. Nenhum chunk encontrado.")
        else:
            st.success(f"Total de chunks encontrados no banco: {len(documents)}")

            # --- COMENTÁRIO ATUALIZADO ---
            # Exibe os chunks encontrados
            for i in range(len(documents)):
                doc_text = documents[i]
                source = metadatas[i].get("source", "N/A")
                with st.container(border=True):
                    st.markdown(f"**Chunk {i+1}**")
                    st.caption(f"Fonte: {source}")
                    st.text(f"{doc_text[:350]}...")


def run_export_xml(retriever: VectorRetriever):
    """Lógica da UI para o Modo 3: Exportar para XML"""
    st.subheader("Modo 3: Exportar Chunks para XML")
    st.info("O arquivo será salvo na pasta raiz do projeto.")

    if st.button("Gerar Arquivo 'chunks_exportados.xml'"):
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        output_filename = "chunks_exportados.xml"
        output_path = os.path.join(SCRIPT_DIR, output_filename)

        with st.spinner("Exportando chunks para XML..."):
            # --- COMENTÁRIO ATUALIZADO ---
            # Lógica de exportação

            # 1. Obter dados
            data = retriever.get_all_chunks()
            documents = data.get("documents")
            metadatas = data.get("metadatas")

            if not documents:
                st.error("O banco de dados está vazio. Nada para exportar.")
                return

            total_chunks = len(documents)

            # 2. Construir XML
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
                metadados_el = ET.SubElement(item, "metadatos")
                for key, value in meta.items():
                    meta_key_el = ET.SubElement(metadados_el, key.replace(" ", "_"))
                    meta_key_el.text = str(value)

            # 3. Formatar e Salvar
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
    """Lógica da UI para o Modo 4: Encerrar"""
    st.subheader("Modo 4: Encerrar Servidor")
    st.warning("Clicar neste botão encerrará este servidor Streamlit.")

    if st.button("Encerrar Aplicação"):
        st.success("Encerrando servidor...")
        print("Comando de encerramento recebido da UI.")
        os._exit(0)  # Força a parada do processo Python


# --- Ponto de Entrada Principal da Aplicação ---
def main():
    st.set_page_config(page_title="Validação do VectorDB", layout="wide")
    st.title("Ferramenta de Validação do Banco de Vetores (ChromaDB)")
    # --- CAPTION ATUALIZADO ---
    st.caption(
        "Interface de auditoria para o VectorDB (baseado em 'vector_retriever.py' e 'ingest.py')"
    )

    # Inicializa o retriever (usando o cache)
    retriever = initialize_retriever()

    # --- Barra Lateral de Navegação ---
    st.sidebar.title("Opções de Validação")
    opcoes = [
        "1. Testar Busca (Re-Ranking)",
        "2. Listar Todos os Chunks",
        "3. Exportar Chunks para XML",
        "4. Encerrar Servidor",
    ]
    modo = st.sidebar.radio(
        "Selecione uma operação:", opcoes, label_visibility="collapsed"
    )

    # --- Exibe a página correta baseada na seleção ---
    if modo == opcoes[0]:
        run_search_test(retriever)

    elif modo == opcoes[1]:
        run_list_all(retriever)

    elif modo == opcoes[2]:
        run_export_xml(retriever)

    elif modo == opcoes[3]:
        run_shutdown()


if __name__ == "__main__":
    main()
