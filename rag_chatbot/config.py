# config.py
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
# Isso é crucial para carregar a GEMINI_API_KEY
load_dotenv()

# --- Definição do Caminho Base ---
# Pega o caminho absoluto do diretório onde este arquivo (config.py) está.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Configurações de Caminhos ---
# Ajuste os caminhos para serem relativos ao BASE_DIR (a raiz do projeto)
DOCS_DIR = os.path.join(BASE_DIR, "docs")
VECTOR_DB_DIR = os.path.join(BASE_DIR, "vector_db")
MODEL_DIR = os.path.join(BASE_DIR, "models")

# --- Configuração do LLM (Gemini) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = "gemini-2.5-flash"  # Use "gemini-pro" se preferir a versão 1.0

# --- Configuração do Modelo de Embedding ---
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# --- Modelo usado para o re-ranking (CrossEncoder)
# RERANKER_MODEL_NAME = "sentence-transformers/ms-marco-MiniLM-L-6-v2"
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L6-v2"
# --- Configuração da Busca (Retriever) ---
SEARCH_K_RAW = 20  # Quantos chunks buscar inicialmente
SEARCH_K_FINAL = 3  # Quantos chunks selecionar após o re-ranking
