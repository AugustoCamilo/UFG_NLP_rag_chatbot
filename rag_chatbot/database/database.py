# database.py
import sqlite3

def init_db():
    """Inicializa o banco de dados e cria as tabelas se não existirem."""
    conn = sqlite3.connect('chat_solution.db')
    cursor = conn.cursor()

    # Tabela para histórico de chat
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        user_message TEXT NOT NULL,
        bot_response TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Tabela para feedback
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL,
        rating TEXT NOT NULL, -- 'like' ou 'dislike'
        comment TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (message_id) REFERENCES chat_history (id)
    )
    ''')

    conn.commit()
    conn.close()
    print("Banco de dados 'chat_solution.db' inicializado com sucesso.")

if __name__ == '__main__':
    init_db()