# read_db.py
import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime  # <<< NOVO IMPORT

# Importar o arquivo de configuração
import config


# --- NOVO IMPORT E INICIALIZAÇÃO DO RE-RANKER ---
from sentence_transformers import CrossEncoder

# Carrega o modelo de Re-Ranker (Cross-Encoder)
# Isso pode levar alguns segundos na primeira vez
try:
    print("Carregando modelo de Re-Ranking (Cross-Encoder)...")
    reranker = CrossEncoder(config.RERANKER_MODEL_NAME)  #
    print("Modelo Re-Ranker carregado com sucesso.")
except Exception as e:
    print(f"Erro ao carregar o modelo Re-Ranker: {e}")  #
    print(
        "Verifique sua conexão com a internet ou a instalação do sentence-transformers."
    )
    reranker = None  #
# --- FIM DA NOVA INICIALIZAÇÃO ---


# --- CAMINHOS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  #


def load_database():
    """Carrega o banco de vetores existente."""
    if not os.path.exists(config.VECTOR_DB_DIR):  #
        print(
            f"Erro: Diretório do banco de vetores não encontrado em '{config.VECTOR_DB_DIR}'"
        )
        return None

    try:
        print("Inicializando modelo de embedding...")
        embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_NAME)  #

        print(f"Carregando banco de vetores de '{config.VECTOR_DB_DIR}'...")
        vectordb = Chroma(
            persist_directory=config.VECTOR_DB_DIR, embedding_function=embeddings
        )  #
        print("Banco de vetores carregado com sucesso.")
        return vectordb

    except Exception as e:
        print(f"Ocorreu um erro ao carregar o banco de dados: {e}")  #
        return None


def read_all_chunks(vectordb):
    """Lê e exibe (parcialmente) todos os chunks."""
    print("\n--- [MODO 1: Lendo Todos os Chunks Armazenados] ---")

    data = vectordb.get()  #
    documents = data.get("documents")  #
    metadatas = data.get("metadatas")  #

    if not documents:  #
        print("O banco de dados está vazio. Nenhum chunk encontrado.")
        return

    print(f"Total de chunks encontrados no banco: {len(documents)}")

    for i in range(len(documents)):
        doc_text = documents[i]
        source = metadatas[i].get("source", "N/A")  #

        print("\n" + "=" * 50)
        print(f"Chunk {i+1} (Fonte: {source})")
        print("=" * 50)
        print(f"{doc_text[:350]}...")

    print("\n" + "=" * 50)
    print("Leitura de todos os chunks concluída.")


# --- FUNÇÃO DE BUSCA TOTALMENTE MODIFICADA ---
def search_chunks(vectordb, query):
    """
    Executa uma busca vetorial (Recall) seguida por um
    Re-Ranking (Precision) para encontrar os melhores chunks.
    """
    print(f"\n--- [MODO 2: Testando Busca com Re-Ranking] ---")

    if not query:  #
        print("Nenhuma query (pergunta) fornecida para a busca.")
        return

    if reranker is None:  #
        print("O Re-Ranker não foi carregado. Impossível realizar a busca.")
        return

    # ETAPA 1: RECALL (Busca Vetorial Rápida)
    print(
        f"Etapa 1: Buscando por: '{query}' (Recuperando {config.SEARCH_K_RAW} chunks...)"
    )  #
    try:
        results_with_scores = vectordb.similarity_search_with_score(
            query, k=config.SEARCH_K_RAW
        )  #

        if not results_with_scores:  #
            print("Nenhum resultado relevante encontrado na busca vetorial.")
            return

    except Exception as e:
        print(f"Ocorreu um erro durante a busca vetorial: {e}")  #
        return

    # ETAPA 2: RE-RANKING (Reclassificação Inteligente)
    print(
        f"Etapa 2: Re-Rankeando os {len(results_with_scores)} resultados (pode levar um momento)..."
    )  #

    try:
        # 1. Criar pares de [pergunta, chunk] para o Re-Ranker
        pairs = [[query, doc.page_content] for doc, score in results_with_scores]  #

        # 2. Obter os novos scores do Re-Ranker
        rerank_scores = reranker.predict(pairs)  #

        # 3. Combinar os documentos com seus novos scores
        reranked_results = list(zip(results_with_scores, rerank_scores))  #

        # 4. Ordenar pelos novos scores (MAIOR é MELHOR)
        reranked_results.sort(key=lambda x: x[1], reverse=True)  #

        # 5. Pegar o Top-K final
        top_k_results = reranked_results[: config.SEARCH_K_FINAL]  #

    except Exception as e:
        print(f"Ocorreu um erro durante o Re-Ranking: {e}")  #
        return

    # ETAPA 3: EXIBIR RESULTADOS
    print(
        f"\nExibindo os {config.SEARCH_K_FINAL} resultados MAIS RELEVANTES"
        f" (de {config.SEARCH_K_RAW} analisados):"
    )  #

    for i, ((doc, old_score), rerank_score) in enumerate(top_k_results):
        source = doc.metadata.get("source", "N/A")  #
        page = doc.metadata.get("page", "N/A")  #

        print("\n" + "-" * 50)
        print(
            f"Resultado Relevante {i+1} (Fonte: {source} | Página: {page})"
            f"\n(Score de Relevância: {rerank_score:.4f})"
        )
        print("-" * 50)
        print(doc.page_content)


# --- FIM DA FUNÇÃO MODIFICADA ---


# --- FUNÇÃO DE EXPORTAÇÃO MODIFICADA ---
def export_chunks_to_xml(vectordb):
    """
    Exporta todos os chunks e seus metadados para um arquivo XML.
    (Esta função permanece inalterada)
    """
    print("\n--- [MODO 3: Exportando Chunks para XML] ---")

    # 1. Obter todos os dados do banco
    data = vectordb.get()  #
    documents = data.get("documents")  #
    metadatas = data.get("metadatas")  #

    if not documents:  #
        print("O banco de dados está vazio. Nenhum chunk para exportar.")
        return

    total_chunks = len(documents)
    print(f"Iniciando exportação de {total_chunks} chunks...")

    # 2. Definir o caminho do arquivo de saída
    output_filename = "chunks_exportados.xml"
    output_path = os.path.join(SCRIPT_DIR, output_filename)  #

    # 3. Construir a estrutura XML
    root = ET.Element("dados_chunks")  #

    # --- INÍCIO DA ALTERAÇÃO ---
    # 3.1. Criar e adicionar o comentário de metadados
    now = datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
    comment_text = (
        f" Exportação gerada em: {timestamp_str}. Total de chunks: {total_chunks} "
    )
    comment = ET.Comment(comment_text)
    root.insert(0, comment)  # Insere o comentário como o primeiro item
    # --- FIM DA ALTERAÇÃO ---

    for i in range(len(documents)):
        doc_text = documents[i]
        meta = metadatas[i]

        # Criar o elemento <item> para cada chunk
        item = ET.SubElement(root, "item")  #

        # Adicionar ID do chunk
        chunk_id_el = ET.SubElement(item, "chunk_id")  #
        chunk_id_el.text = str(i + 1)  #

        # Adicionar o conteúdo (texto)
        conteudo_el = ET.SubElement(item, "conteudo")  #
        conteudo_el.text = doc_text  #

        # Adicionar o nó de metadados
        metadados_el = ET.SubElement(item, "metadados")  #
        for key, value in meta.items():
            # Cria uma tag com o nome da chave (ex: <source>)
            meta_key_el = ET.SubElement(metadados_el, key.replace(" ", "_"))  #
            meta_key_el.text = str(value)  #

    # 4. Formatar e salvar o arquivo XML (com "pretty print")
    try:
        # Converte a árvore XML para uma string
        xml_string = ET.tostring(root, "utf-8")  #

        # Usa minidom para re-formatar a string com indentação
        parsed_string = minidom.parseString(xml_string)  #
        pretty_xml = parsed_string.toprettyxml(indent="  ", encoding="utf-8")  #

        # Salva o arquivo formatado (em modo binário 'wb' por causa do encoding)
        with open(output_path, "wb") as f:  #
            f.write(pretty_xml)  #

        print(f"\nSucesso! {total_chunks} chunks exportados para:")
        print(f"{output_path}")

    except Exception as e:
        print(f"\nErro ao salvar o arquivo XML: {e}")  #


# --- BLOCO PRINCIPAL (Inalterado) ---
if __name__ == "__main__":
    vectordb = load_database()

    if vectordb:  #
        print("\n--- [Modo de Validação de Chunks] ---")
        print("\nInstruções:")
        print("  1. Digite sua consulta (pergunta) para testar a busca.")
        print("  2. Digite '!todos' para listar todos os chunks no banco.")
        print("  3. Digite '!exportar' para salvar todos os chunks em um XML.")
        print("  4. Digite '!sair' para encerrar o script.")

        while True:
            query = input("\nSua consulta (ou '!sair' / '!todos' / '!exportar'): ")  #

            if query.lower() == "!sair":  #
                print("Encerrando o script...")
                break  #
            elif query == "!todos":  #
                read_all_chunks(vectordb)  #
            elif query == "!exportar":  #
                export_chunks_to_xml(vectordb)  #
            elif query.strip() == "":  #
                print("Por favor, digite uma consulta válida.")
            else:
                search_chunks(vectordb, query=query)  #
    else:
        print("\nNão foi possível carregar o banco de dados. Encerrando.")
        sys.exit(1)  #
