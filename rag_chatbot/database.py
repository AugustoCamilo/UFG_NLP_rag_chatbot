# database.py
import sqlite3
import os

# Define o diretório base (onde este script está)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Define o nome da pasta para o banco de dados
DB_DIR = os.path.join(BASE_DIR, "database")
# Define o caminho completo para o arquivo do banco de dados
DB_PATH = os.path.join(DB_DIR, "chat_solution.db")


def init_db():
    """Inicializa o banco de dados e cria as tabelas se não existirem."""

    # Garante que o diretório 'database' exista antes de tentar conectar
    try:
        os.makedirs(DB_DIR, exist_ok=True)
    except OSError as e:
        print(f"Erro ao criar o diretório do banco de dados em {DB_DIR}: {e}")
        return

    # Conecta ao banco de dados usando o caminho completo (DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- ESQUEMA DA TABELA ATUALIZADO ---
    # Tabela para histórico de chat
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        user_message TEXT NOT NULL,
        bot_response TEXT NOT NULL,
        
        -- Contadores
        user_chars INTEGER,
        bot_chars INTEGER,
        user_tokens INTEGER,
        bot_tokens INTEGER,
        
        -- Timestamps
        request_start_time DATETIME,
        retrieval_end_time DATETIME,
        response_end_time DATETIME,
        
        -- Durações (em segundos)
        retrieval_duration_sec REAL,
        generation_duration_sec REAL,
        total_duration_sec REAL
    )
    """
    )
    # --- FIM DA ATUALIZAÇÃO ---

    # Tabela para feedback (inalterada)
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
    )

    conn.commit()
    conn.close()

    print(f"Banco de dados inicializado com sucesso em: {DB_PATH}")


if __name__ == "__main__":
    init_db()
