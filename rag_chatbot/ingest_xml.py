# ingest_xml.py
"""
Módulo de Ingestão de Chunks Pré-Processados (XML).

Este script substitui o processo de leitura de PDFs e divisão de texto (splitting).
Ele lê arquivos XML que já contêm os chunks processados semanticamente (Pergunta/Resposta),
conforme gerado externamente, e popula o banco vetorial ChromaDB.

---
### Regras de Negócio
---
1. **Leitura de XML:** Itera sobre todos os arquivos .xml na pasta `config.DOCS_DIR`.
2. **Ignora Chunk ID:** O campo <chunk_id> do XML é ignorado para evitar conflitos.
   O ChromaDB gerará IDs automáticos.
3. **Metadados Dinâmicos:** Todos os campos dentro da tag <metadados> são capturados.
4. **Sanitização:** O campo 'source' nos metadados é convertido para caminho relativo,
   mantendo a segurança e consistência com o script original.
5. **Recriação do Banco:** Assim como o ingest original, este script APAGA o banco atual
   e cria um novo com base nos XMLs encontrados.
"""

import os
import shutil
import xml.etree.ElementTree as ET
from tqdm import tqdm
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# Importar o arquivo de configuração existente
import config

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
        for item in root.findall('item'):
            # 1. Extrair Conteúdo
            conteudo_node = item.find('conteudo')
            if conteudo_node is None or not conteudo_node.text:
                continue # Pula itens vazios
            
            page_content = conteudo_node.text.strip()
            
            # 2. Extrair Metadados
            metadata = {}
            metadados_node = item.find('metadados')
            
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
                        metadata["source"] = os.path.relpath(metadata["source"], config.BASE_DIR)
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
    xml_files = [f for f in os.listdir(config.DOCS_DIR) if f.endswith(".xml")]

    if not xml_files:
        print(f"Nenhum arquivo XML encontrado no diretório: {config.DOCS_DIR}")
        return

    print(f"Encontrados {len(xml_files)} arquivos XML.")

    # 2. Carregar e Converter XMLs para Documents
    all_docs = []
    
    for filename in tqdm(xml_files, desc="Lendo XMLs", unit="arquivo"):
        filepath = os.path.join(config.DOCS_DIR, filename)
        docs_from_file = parse_xml_to_documents(filepath)
        all_docs.extend(docs_from_file)

    if not all_docs:
        print("Nenhum chunk válido encontrado nos arquivos XML.")
        return

    print(f"Total de chunks carregados: {len(all_docs)}")

    # 3. Inicializar modelo de embedding
    print(f"Carregando modelo de embedding: {config.EMBEDDING_MODEL_NAME}")
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_NAME)

    # 4. Limpar o banco de dados vetorial antigo
    print(f"Limpando banco de dados antigo em: {config.VECTOR_DB_DIR}")
    if os.path.isdir(config.VECTOR_DB_DIR):
        try:
            shutil.rmtree(config.VECTOR_DB_DIR)
        except OSError as e:
            print(f"Erro ao remover diretório do banco: {e}")
            return
    
    # 5. Criar e persistir o banco de dados vetorial
    print("Gerando Embeddings e populando o ChromaDB...")
    
    # Batch size pode ser ajustado se houver erro de memória, mas Chroma gerencia bem
    vectordb = Chroma.from_documents(
        documents=all_docs,
        embedding=embeddings,
        persist_directory=config.VECTOR_DB_DIR,
    )

    print(f"Sucesso! Banco de vetores recriado em '{config.VECTOR_DB_DIR}' a partir dos XMLs.")

if __name__ == "__main__":
    process_documents_from_xml()