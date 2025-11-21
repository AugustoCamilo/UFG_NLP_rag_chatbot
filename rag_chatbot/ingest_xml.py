# ingest_xml.py

import os
import shutil
import time
import xml.etree.ElementTree as ET
from tqdm import tqdm
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# Importar o arquivo de configuração existente
from settings import settings


def parse_xml_to_documents(xml_path):
    """
    Lê um arquivo XML e converte seus itens em objetos Document do LangChain.
    Ignora o 'chunk_id' original.
    """
    documents = []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Itera sobre cada <item> no XML
        for item in root.findall("item"):
            # 1. Extrair Conteúdo
            conteudo_node = item.find("conteudo")
            if conteudo_node is None or not conteudo_node.text:
                continue  # Pula itens vazios

            page_content = conteudo_node.text.strip()

            # 2. Extrair Metadados
            metadata = {}
            metadados_node = item.find("metadados")

            if metadados_node is not None:
                for meta_item in metadados_node:
                    # Adiciona chave/valor ao dicionário de metadados
                    # O Chroma exige strings, int ou float. Vamos manter como string ou converter se necessário.
                    if meta_item.text:
                        metadata[meta_item.tag] = meta_item.text.strip()

            # 3. Sanitização de Segurança (Igual ao ingest.py original)
            # Converte caminhos absolutos em 'source' para relativos
            if "source" in metadata:
                try:
                    # Se o caminho for absoluto, torna relativo à raiz do projeto
                    if os.path.isabs(metadata["source"]):
                        metadata["source"] = os.path.relpath(
                            metadata["source"], settings.BASE_DIR
                        )
                except ValueError:
                    # Caso o caminho esteja em uma unidade diferente (Windows), mantém como está
                    pass

            # Cria o objeto Document
            # Nota: Não passamos 'id' aqui, o Chroma vai gerar um UUID.
            doc = Document(page_content=page_content, metadata=metadata)
            documents.append(doc)

    except ET.ParseError as e:
        print(f"Erro ao processar XML {xml_path}: {e}")
    except Exception as e:
        print(f"Erro genérico ao ler {xml_path}: {e}")

    return documents


def process_documents_from_xml():
    """Lê XMLs, cria documentos e vetoriza no ChromaDB."""
    print("Iniciando a ingestão via XML (Chunking Semântico)...")

    # 1. Listar arquivos XML
    xml_files = [f for f in os.listdir(settings.DOCS_DIR) if f.endswith(".xml")]

    if not xml_files:
        print(f"Nenhum arquivo XML encontrado no diretório: {settings.DOCS_DIR}")
        return

    print(f"Encontrados {len(xml_files)} arquivos XML.")

    # 2. Carregar e Converter XMLs para Documents
    all_docs = []

    for filename in tqdm(xml_files, desc="Lendo XMLs", unit="arquivo"):
        filepath = os.path.join(settings.DOCS_DIR, filename)
        docs_from_file = parse_xml_to_documents(filepath)
        all_docs.extend(docs_from_file)

    if not all_docs:
        print("Nenhum chunk válido encontrado nos arquivos XML.")
        return

    print(f"Total de chunks carregados: {len(all_docs)}")

    # 3. Inicializar modelo de embedding
    print(f"Carregando modelo de embedding: {settings.EMBEDDING_MODEL_NAME}")
    embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL_NAME)

    # 4. Limpar o banco de dados vetorial antigo
    print(f"Limpando banco de dados antigo em: {settings.VECTOR_DB_DIR}")
    if os.path.isdir(settings.VECTOR_DB_DIR):
        try:
            shutil.rmtree(settings.VECTOR_DB_DIR)
            # Pequena pausa para o OS liberar o file handle
            time.sleep(1)
        except PermissionError:
            print("ERRO CRÍTICO: Não foi possível apagar a pasta do banco de dados.")
            print(
                "Motivo: O banco de dados está em uso por outro processo (provavelmente o Streamlit)."
            )
            print("SOLUÇÃO: Feche o terminal do 'streamlit run' e tente novamente.")
            return  # PARE a execução aqui para não corromper mais
        except OSError as e:
            print(f"Erro ao remover diretório do banco: {e}")
            return

    # Verificação extra
    if os.path.exists(settings.VECTOR_DB_DIR):
        print(
            "Erro: O diretório ainda existe. A ingestão foi abortada para evitar corrupção."
        )
        return

    # 5. Criar e persistir o banco de dados vetorial
    print("Gerando Embeddings e populando o ChromaDB...")

    # Batch size pode ser ajustado se houver erro de memória, mas Chroma gerencia bem
    vectordb = Chroma.from_documents(
        documents=all_docs,
        embedding=embeddings,
        persist_directory=settings.VECTOR_DB_DIR,
    )

    print(
        f"Sucesso! Banco de vetores recriado em '{settings.VECTOR_DB_DIR}' a partir dos XMLs."
    )


if __name__ == "__main__":
    process_documents_from_xml()
