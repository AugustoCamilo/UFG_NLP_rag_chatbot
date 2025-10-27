# read_db_vector.py
import os
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime

# Importar o arquivo de configuração
import config

# --- IMPORT PRINCIPAL ATUALIZADO ---
# Removemos Chroma, HuggingFaceEmbeddings e CrossEncoder
# Adicionamos o nosso VectorRetriever
from vector_retriever import VectorRetriever

# --- FIM DA ATUALIZAÇÃO ---


# --- CAMINHOS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# --- FUNÇÃO ATUALIZADA ---
def initialize_retriever():
    """Inicializa o VectorRetriever centralizado."""
    try:
        # Instancia nossa classe que carrega todos os modelos
        retriever = VectorRetriever()
        return retriever
    except Exception as e:
        print(f"Ocorreu um erro ao inicializar o VectorRetriever: {e}")
        return None


# --- FIM DA ATUALIZAÇÃO ---


# --- FUNÇÃO ATUALIZADA ---
def read_all_chunks(retriever: VectorRetriever):
    """Lê e exibe (parcialmente) todos os chunks."""
    print("\n--- [MODO 1: Lendo Todos os Chunks Armazenados] ---")

    # Usa o novo método do retriever para obter os dados
    data = retriever.get_all_chunks()
    documents = data.get("documents")
    metadatas = data.get("metadatas")

    if not documents:
        print("O banco de dados está vazio. Nenhum chunk encontrado.")
        return

    print(f"Total de chunks encontrados no banco: {len(documents)}")

    for i in range(len(documents)):
        doc_text = documents[i]
        source = metadatas[i].get("source", "N/A")

        print("\n" + "=" * 50)
        print(f"Chunk {i+1} (Fonte: {source})")
        print("=" * 50)
        print(f"{doc_text[:350]}...")

    print("\n" + "=" * 50)
    print("Leitura de todos os chunks concluída.")


# --- FIM DA ATUALIZAÇÃO ---


# --- FUNÇÃO DE BUSCA TOTALMENTE REFEITA ---
def search_chunks(retriever: VectorRetriever, query: str):
    """
    Executa a busca centralizada usando o VectorRetriever
    para encontrar os melhores chunks.
    """
    print(f"\n--- [MODO 2: Testando Busca com Re-Ranking] ---")

    if not query:
        print("Nenhuma query (pergunta) fornecida para a busca.")
        return

    # ETAPAS 1 E 2: RECALL E RE-RANKING (AGORA CENTRALIZADOS)
    # Chama o novo método que retorna os scores
    try:
        top_k_results = retriever.retrieve_context_with_scores(query)

        if not top_k_results:
            print("Nenhum resultado relevante encontrado.")
            return

    except Exception as e:
        print(f"Ocorreu um erro durante a busca: {e}")
        return

    # ETAPA 3: EXIBIR RESULTADOS
    print(f"\nExibindo os {len(top_k_results)} resultados MAIS RELEVANTES:")

    # O loop agora é mais simples, pois `top_k_results` é List[(Document, float)]
    for i, (doc, rerank_score) in enumerate(top_k_results):
        source = doc.metadata.get("source", "N/A")
        page = doc.metadata.get("page", "N/A")

        print("\n" + "-" * 50)
        print(
            f"Resultado Relevante {i+1} (Fonte: {source} | Página: {page})"
            f"\n(Score de Relevância: {rerank_score:.4f})"
        )
        print("-" * 50)
        print(doc.page_content)


# --- FIM DA FUNÇÃO REFEITA ---


# --- FUNÇÃO ATUALIZADA ---
def export_chunks_to_xml(retriever: VectorRetriever):
    """
    Exporta todos os chunks e seus metadados para um arquivo XML.
    """
    print("\n--- [MODO 3: Exportando Chunks para XML] ---")

    # 1. Obter todos os dados do banco
    # Usa o novo método do retriever para obter os dados
    data = retriever.get_all_chunks()
    documents = data.get("documents")
    metadatas = data.get("metadatas")

    if not documents:
        print("O banco de dados está vazio. Nenhum chunk para exportar.")
        return

    total_chunks = len(documents)
    print(f"Iniciando exportação de {total_chunks} chunks...")

    # 2. Definir o caminho do arquivo de saída
    output_filename = "chunks_exportados.xml"
    output_path = os.path.join(SCRIPT_DIR, output_filename)

    # 3. Construir a estrutura XML
    root = ET.Element("dados_chunks")

    # 3.1. Criar e adicionar o comentário de metadados
    now = datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
    comment_text = (
        f" Exportação gerada em: {timestamp_str}. Total de chunks: {total_chunks} "
    )
    comment = ET.Comment(comment_text)
    root.insert(0, comment)  # Insere o comentário como o primeiro item

    for i in range(len(documents)):
        doc_text = documents[i]
        meta = metadatas[i]

        # Criar o elemento <item> para cada chunk
        item = ET.SubElement(root, "item")

        # Adicionar ID do chunk
        chunk_id_el = ET.SubElement(item, "chunk_id")
        chunk_id_el.text = str(i + 1)

        # Adicionar o conteúdo (texto)
        conteudo_el = ET.SubElement(item, "conteudo")
        conteudo_el.text = doc_text

        # Adicionar o nó de metadados
        metadados_el = ET.SubElement(item, "metadados")
        for key, value in meta.items():
            # Cria uma tag com o nome da chave (ex: <source>)
            meta_key_el = ET.SubElement(metadados_el, key.replace(" ", "_"))
            meta_key_el.text = str(value)

    # 4. Formatar e salvar o arquivo XML (com "pretty print")
    try:
        # Converte a árvore XML para uma string
        xml_string = ET.tostring(root, "utf-8")

        # Usa minidom para re-formatar a string com indentação
        parsed_string = minidom.parseString(xml_string)
        pretty_xml = parsed_string.toprettyxml(indent="  ", encoding="utf-8")

        # Salva o arquivo formatado (em modo binário 'wb' por causa do encoding)
        with open(output_path, "wb") as f:
            f.write(pretty_xml)

        print(f"\nSucesso! {total_chunks} chunks exportados para:")
        print(f"{output_path}")

    except Exception as e:
        print(f"\nErro ao salvar o arquivo XML: {e}")


# --- FIM DA ATUALIZAÇÃO ---


# --- BLOCO PRINCIPAL ATUALIZADO ---
if __name__ == "__main__":
    # Renomeado para `retriever`
    retriever = initialize_retriever()

    if retriever:
        print("\n--- [Modo de Validação de Chunks] ---")
        print("\nInstruções:")
        print("  1. Digite sua consulta (pergunta) para testar a busca.")
        print("  2. Digite '!todos' para listar todos os chunks no banco.")
        print("  3. Digite '!exportar' para salvar todos os chunks em um XML.")
        print("  4. Digite '!sair' para encerrar o script.")

        while True:
            query = input("\nSua consulta (ou '!sair' / '!todos' / '!exportar'): ")

            if query.lower() == "!sair":
                print("Encerrando o script...")
                break
            elif query == "!todos":
                read_all_chunks(retriever)  # Passa o retriever
            elif query == "!exportar":
                export_chunks_to_xml(retriever)  # Passa o retriever
            elif query.strip() == "":
                print("Por favor, digite uma consulta válida.")
            else:
                search_chunks(retriever, query=query)  # Passa o retriever
    else:
        print("\nNão foi possível inicializar o retriever. Encerrando.")
        sys.exit(1)
# --- FIM DA ATUALIZAÇÃO ---
