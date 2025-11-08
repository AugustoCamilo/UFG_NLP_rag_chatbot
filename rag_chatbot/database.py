# database.py
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
    # (Inalterada)
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL,
        rating TEXT NOT NULL, -- 'like' ou 'dislike'
        comment TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (message_id) REFERENCES chat_history (id)
    )
    """
    )  #

    # --- INÍCIO DAS NOVAS TABELAS DE AVALIAÇÃO ---

    # Tabela 1: Armazena cada "Rodada de Validação"
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS validation_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        query TEXT NOT NULL,
        search_type TEXT NOT NULL, -- 'vector_only' ou 'reranked'
        
        -- Métricas calculadas
        hit_rate_eval INTEGER, -- 0 (Erro) ou 1 (Acerto)
        mrr_eval REAL          -- 0, 1, 0.5, 0.33, etc.
    )
    """
    )

    # Tabela 2: Armazena os chunks que foram retornados em cada rodada
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
    # --- FIM DAS NOVAS TABELAS ---

    conn.commit()  #
    conn.close()  #

    print(f"Banco de dados inicializado com sucesso em: {DB_PATH}")  #


if __name__ == "__main__":
    init_db()  #
