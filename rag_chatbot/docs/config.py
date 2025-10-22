# config.py
import os

# --- Definição do Caminho Base ---
# Pega o caminho absoluto do diretório onde este arquivo (config.py) está.
# Isso torna os outros caminhos robustos, não importa de onde o script é chamado.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Configurações de Caminhos ---
# O diretório de documentos é o próprio diretório base.
DOCS_DIR = BASE_DIR

# O diretório do banco vetorial é um nível acima, na pasta 'vector_db'
# os.path.join constrói o caminho de forma segura (funciona no Windows, Linux, Mac)
VECTOR_DB_DIR = os.path.abspath(os.path.join(BASE_DIR, '../vector_db'))

# --- Configuração do Modelo de Embedding ---
# Este é o nome do modelo que ambos os scripts usarão.
EMBEDDING_MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'

# --- Configuração da Busca ---
# (Bônus) Centralizando também os parâmetros de busca
SEARCH_K_RAW = 20  # Quantos chunks buscar inicialmente
SEARCH_K_FINAL = 3  # Quantos chunks exibir no final