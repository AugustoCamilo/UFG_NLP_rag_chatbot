# read_db_history.py
import sqlite3
import os
import sys
import csv
from datetime import datetime

# Importar o arquivo de configuração do banco de dados
# para obter o caminho (DB_PATH)
import database as history_db


def connect_to_db():
    """Conecta ao banco de dados SQLite do histórico."""

    # Usa o DB_PATH do arquivo database.py
    db_path = history_db.DB_PATH

    if not os.path.exists(db_path):
        print(f"Erro: Arquivo do banco de dados não encontrado em '{db_path}'")
        print("Por favor, execute 'python database.py' primeiro para criá-lo.")
        return None

    try:
        # Conecta ao banco de dados
        conn = sqlite3.connect(db_path)
        print(f"Conectado com sucesso ao banco de dados: {db_path}")
        return conn

    except Exception as e:
        print(f"Ocorreu um erro ao conectar ao banco de dados: {e}")
        return None


def read_all_history(conn):
    """Lê e exibe todas as entradas de histórico do chat."""
    print("\n--- [MODO 1: Lendo Todo o Histórico] ---")

    try:
        cursor = conn.cursor()
        # Seleciona todas as colunas da tabela chat_history
        cursor.execute(
            """
            SELECT id, session_id, user_message, bot_response, total_tokens, total_chars, timestamp 
            FROM chat_history 
            ORDER BY timestamp ASC
        """
        )

        rows = cursor.fetchall()

        if not rows:
            print("O banco de dados de histórico está vazio.")
            return

        print(f"Total de mensagens encontradas: {len(rows)}")

        for row in rows:
            (id, session_id, user_msg, bot_msg, tokens, chars, timestamp) = row

            print("\n" + "=" * 50)
            print(f"ID: {id} | Sessão: {session_id}")
            print(f"Data: {timestamp} | Tokens: {tokens} | Chars: {chars}")
            print("-" * 50)
            print(f"  USUÁRIO: {user_msg}")
            print(f"ASSISTENTE: {bot_msg}")

        print("\n" + "=" * 50)
        print("Leitura de todo o histórico concluída.")

    except Exception as e:
        print(f"Erro ao ler o histórico: {e}")


def search_by_session(conn, session_id):
    """Busca e exibe o histórico de um session_id específico."""
    print(f"\n--- [MODO 2: Buscando pela Sessão: {session_id}] ---")

    if not session_id or not session_id.strip():
        print("Nenhum ID de sessão fornecido.")
        return

    try:
        cursor = conn.cursor()
        # Seleciona as colunas filtrando por session_id
        cursor.execute(
            """
            SELECT id, user_message, bot_response, total_tokens, total_chars, timestamp 
            FROM chat_history 
            WHERE session_id = ? 
            ORDER BY timestamp ASC
        """,
            (session_id.strip(),),
        )

        rows = cursor.fetchall()

        if not rows:
            print(f"Nenhum histórico encontrado para a sessão: '{session_id}'")
            return

        print(f"Total de mensagens encontradas para esta sessão: {len(rows)}")

        for row in rows:
            (id, user_msg, bot_msg, tokens, chars, timestamp) = row

            print("\n" + "-" * 50)
            print(f"ID: {id} | Data: {timestamp}")
            print(f"Tokens: {tokens} | Chars: {chars}")
            print("-" * 50)
            print(f"  USUÁRIO: {user_msg}")
            print(f"ASSISTENTE: {bot_msg}")

        print("\n" + "-" * 50)
        print(f"Fim do histórico para a sessão: {session_id}")

    except Exception as e:
        print(f"Erro ao buscar pela sessão: {e}")


def list_sessions(conn):
    """Lista todos os session_ids únicos, a contagem de msgs e a última atividade."""
    print("\n--- [MODO 3: Listando Todas as Sessões] ---")

    try:
        cursor = conn.cursor()
        # Agrupa por session_id para auditoria
        cursor.execute(
            """
            SELECT session_id, COUNT(*) as msg_count, MAX(timestamp) as last_activity
            FROM chat_history 
            GROUP BY session_id
            ORDER BY last_activity DESC
        """
        )

        rows = cursor.fetchall()

        if not rows:
            print("Nenhuma sessão encontrada no histórico.")
            return

        print(f"Total de sessões únicas encontradas: {len(rows)}")
        print("\n" + "-" * 70)
        print(f"{'ID DA SESSÃO':<38} | {'MSGS':<5} | {'ÚLTIMA ATIVIDADE':<20}")
        print("-" * 70)

        for row in rows:
            (session_id, msg_count, last_activity) = row
            print(f"{session_id:<38} | {msg_count:<5} | {last_activity:<20}")

        print("-" * 70)

    except Exception as e:
        print(f"Erro ao listar sessões: {e}")


def export_history_to_csv(conn):
    """Exporta todo o histórico do chat para um arquivo CSV."""
    print("\n--- [MODO 4: Exportando Histórico para CSV] ---")

    output_filename = "historico_chat_exportado.csv"
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), output_filename
    )

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chat_history ORDER BY timestamp ASC")

        rows = cursor.fetchall()
        if not rows:
            print("Nada para exportar, o histórico está vazio.")
            return

        # Obter nomes das colunas
        headers = [description[0] for description in cursor.description]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)  # Escreve o cabeçalho
            writer.writerows(rows)  # Escreve os dados

        print(f"\nSucesso! {len(rows)} mensagens exportadas para:")
        print(f"{output_path}")

    except Exception as e:
        print(f"\nErro ao salvar o arquivo CSV: {e}")


if __name__ == "__main__":
    conn = connect_to_db()

    if conn:
        print("\n--- [Modo de Auditoria de Histórico] ---")
        print("\nInstruções:")
        print("  1. Digite um ID de sessão para ver o histórico (ex: 172f1ed9-...)")
        print("  2. Digite '!sessoes' para listar todos os IDs de sessão únicos.")
        print(
            "  3. Digite '!todas' para listar *todas* as mensagens de todas as sessões."
        )
        print("  4. Digite '!exportar' para salvar todo o histórico em um CSV.")
        print("  5. Digite '!sair' para encerrar o script.")

        try:
            while True:
                query = input(
                    "\nSua consulta (ou '!sair' / '!sessoes' / '!todas' / '!exportar'): "
                )

                if query.lower() == "!sair":
                    print("Encerrando o script...")
                    break
                elif query.lower() == "!sessoes":
                    list_sessions(conn)
                elif query.lower() == "!todas":
                    read_all_history(conn)
                elif query.lower() == "!exportar":
                    export_history_to_csv(conn)
                elif query.strip() == "":
                    print("Por favor, digite uma consulta válida.")
                else:
                    # Qualquer outra string é tratada como um session_id
                    search_by_session(conn, query=query)

        except KeyboardInterrupt:
            print("\nEncerrando...")

        finally:
            conn.close()
            print("Conexão com o banco de dados fechada.")

    else:
        print("\nNão foi possível conectar ao banco de dados. Encerrando.")
        sys.exit(1)
