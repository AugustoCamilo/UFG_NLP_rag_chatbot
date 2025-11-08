# config.py
"""
Arquivo de Configuração Central da Aplicação RAG.

Este módulo centraliza todas as variáveis de configuração, caminhos de
diretório, chaves de API e parâmetros de modelo para a aplicação.

O objetivo é evitar "magic strings" (valores fixos) espalhados
pelo código, facilitando a manutenção, a experimentação e a
reconfiguração do sistema.

Principais Seções:
-----------------

1.  **Carregamento de Ambiente (`.env`):**
    * Utiliza `load_dotenv()` para carregar segredos (como a API Key)
        do arquivo `.env`, mantendo-os fora do código-fonte.

2.  **Definição de Caminhos (Paths):**
    * Estabelece um `BASE_DIR` (a raiz do projeto).
    * Define os diretórios de trabalho essenciais (`DOCS_DIR`,
        `VECTOR_DB_DIR`, `MODEL_DIR`) de forma relativa ao
        `BASE_DIR`, garantindo que o projeto funcione em
        diferentes máquinas.

3.  **Configuração do LLM (Gemini):**
    * Define o `GEMINI_API_KEY` (lido do `.env`).
    * Define o `GEMINI_MODEL_NAME` (ex: "gemini-1.5-flash") a ser
        usado pelo `rag_chain.py`.

4.  **Configuração de Modelos (HuggingFace):**
    * `EMBEDDING_MODEL_NAME`: Define o modelo de embedding (ex:
        "all-MiniLM-L6-v2") usado pelo `ingest.py` para vetorizar
        documentos e pelo `vector_retriever.py` para consultar o banco.
    * `RERANKER_MODEL_NAME`: Define o modelo CrossEncoder (ex:
        "ms-marco-MiniLM-L6-v2") usado pelo `vector_retriever.py`
        para a etapa de re-ranking.

5.  **Configuração do Retriever (Busca):**
    * `SEARCH_K_RAW`: Quantidade de chunks que o ChromaDB deve
        recuperar na primeira etapa (Recall).
    * `SEARCH_K_FINAL`: Quantidade final de chunks que o Re-Ranker
        deve selecionar para enviar ao LLM (Etapa de Precisão).
"""


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
