# database.py
"""
Módulo de Inicialização do Banco de Dados SQLite.

Este script é responsável por definir e inicializar a estrutura completa
do banco de dados (`chat_solution.db`) usado pela aplicação.

Ele é executado tanto pelo `app.py` (para garantir que o banco de produção
exista) quanto pelos scripts de validação (`validate_vector_db.py`,
`validate_evaluation.py`).

O comando `CREATE TABLE IF NOT EXISTS` é usado para garantir que
o script possa ser executado com segurança sem apagar dados existentes,
apenas criando as tabelas que estiverem faltando.

---
### Estrutura do Schema (Tabelas)
---

O banco é dividido em duas seções principais:

#### 1. Tabelas de Produção (Usadas pelo `app.py` e `rag_chain.py`):

* **`chat_history`:**
    * Armazena cada interação (pergunta/resposta) de todas as sessões
        de usuário.
    * Inclui métricas de performance (duração, tokens, caracteres)
        para cada chamada ao LLM.
* **`feedback`:**
    * Armazena o feedback do usuário (like/dislike).
    * É vinculada à `chat_history` através da `message_id`
        (chave estrangeira).

#### 2. Tabelas de Avaliação (Usadas pelos scripts de validação):

* **`validation_runs`:**
    * Armazena o "resumo" de cada rodada de teste manual executada
        no `validate_vector_db.py`.
    * Contém a query, o tipo de busca (vetorial vs. re-ranking) e
        as métricas de alto nível calculadas (Hit Rate, MRR, Precisão@K).
* **`validation_retrieved_chunks`:**
    * Armazena *cada chunk individual* que foi retornado durante uma
        rodada de validação.
    * É vinculada à `validation_runs` pela `run_id`.
    * Registra o `score` e se o avaliador marcou aquele
        chunk como correto (`is_correct_eval`).
"""


import sqlite3
import os

# Define o diretório base (onde este script está)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  #
# Define o nome da pasta para o banco de dados
DB_DIR = os.path.join(BASE_DIR, "database")  #
# Define o caminho completo para o arquivo do banco de dados
DB_PATH = os.path.join(DB_DIR, "chat_solution.db")  #


def init_db():
    """Inicializa o banco de dados e cria as tabelas se não existirem."""

    # Garante que o diretório 'database' exista
    try:
        os.makedirs(DB_DIR, exist_ok=True)  #
    except OSError as e:
        print(f"Erro ao criar o diretório do banco de dados em {DB_DIR}: {e}")  #
        return

    conn = sqlite3.connect(DB_PATH)  #
    cursor = conn.cursor()  #

    # --- Tabela de Histórico de Chat (Produção) ---
    # (Inalterada)
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        user_message TEXT NOT NULL,
        bot_response TEXT NOT NULL,
        user_chars INTEGER,
        bot_chars INTEGER,
        user_tokens INTEGER,
        bot_tokens INTEGER,
        request_start_time DATETIME,
        retrieval_end_time DATETIME,
        response_end_time DATETIME,
        retrieval_duration_sec REAL,
        generation_duration_sec REAL,
        total_duration_sec REAL
    )
    """
    )  #

    # --- Tabela de Feedback (Produção) ---
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL,
        rating TEXT NOT NULL, -- 'like' ou 'dislike'
        comment TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (message_id) REFERENCES chat_history (id),
        
        -- Garante que só possa existir UMA avaliação por message_id
        UNIQUE(message_id)
        
    )
    """
    )

    # --- INÍCIO DAS TABELAS DE AVALIAÇÃO ---

    # Tabela 1: Armazena cada "Rodada de Validação"
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS validation_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        query TEXT NOT NULL,
        search_type TEXT NOT NULL, -- 'vector_only' ou 'reranked'
        
        -- Métricas calculadas
        hit_rate_eval INTEGER,      -- 0 (Erro) ou 1 (Acerto)
        mrr_eval REAL,              -- 0, 1, 0.5, 0.33, etc.
        precision_at_k_eval REAL  -- (Ex: 0.66 para 2/3 acertos)
    )
    """
    )  #

    # Tabela 2: validation_retrieved_chunks (inalterada)
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS validation_retrieved_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        rank INTEGER NOT NULL, -- Posição (1, 2, 3...)
        chunk_content TEXT,
        source TEXT,
        page INTEGER,
        score REAL,
        is_correct_eval INTEGER, -- 0 (Errado) ou 1 (Marcado como Correto)
        
        FOREIGN KEY (run_id) REFERENCES validation_runs (id)
    )
    """
    )
    # --- FIM DAS TABELAS DE AVALIAÇÃO ---

    conn.commit()
    conn.close()

    print(f"Banco de dados inicializado com sucesso em: {DB_PATH}")


if __name__ == "__main__":
    init_db()
