# app.py
import sqlite3
import uuid
import os
from flask import Flask, render_template, request, jsonify

# --- ALTERAÇÃO NA IMPORTAÇÃO ---
# Importa a nova função que retorna a instância do processador
from rag_core import get_rag_processor

# --- REMOVIDO ---
# Não precisamos mais formatar mensagens do LangChain aqui
# from langchain_core.messages import HumanMessage, AIMessage

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "chat_solution.db")

# --- ALTERAÇÃO NA INICIALIZAÇÃO ---
# Carrega a instância do processador RAG na inicialização
print("Iniciando a aplicação... Carregando modelos de IA via RagProcessor.")
rag_processor = get_rag_processor()
print("Modelos carregados. Servidor pronto.")
# --- FIM DA ALTERAÇÃO ---


def get_db_connection():
    """Conecta ao banco de dados SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---
# FUNÇÃO REMOVIDA: load_chat_history()
# O novo RagProcessor (baseado no llm.py) não gerencia o histórico de chat.
# O histórico agora é salvo no DB apenas para registro, mas não é
# usado para influenciar a próxima resposta do LLM.
# ---


@app.route("/")
def index():
    """Serve a página principal (index.html)."""
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """Endpoint da API para processar uma mensagem de chat."""
    data = request.json
    user_message = data.get("message")
    session_id = data.get("session_id")

    if not user_message or not session_id:
        return jsonify({"error": "Mensagem ou session_id faltando."}), 400

    print(f"[Session: {session_id}] Recebido: {user_message}")

    # --- LÓGICA DE CHAT ATUALIZADA ---

    # 1. REMOVIDO: Carregamento do histórico
    # chat_history = load_chat_history(session_id)

    # 2. Invocar o Processador RAG (agora sem histórico)
    try:
        # Chama o novo método get_response
        bot_response, source_docs = rag_processor.get_response(user_message)

        # Logar os documentos fonte (opcional, mas útil para debug)
        source_names = [doc.metadata.get("source", "N/A") for doc in source_docs]
        print(
            f"Fontes usadas: {list(set(source_names))}"
        )  # 'set' para evitar duplicatas

    except Exception as e:
        print(f"Erro ao invocar RAG Processor: {e}")
        bot_response = "Ocorreu um erro ao processar sua solicitação."
        return jsonify({"response": bot_response, "message_id": None})

    # --- FIM DA LÓGICA DE CHAT ATUALIZADA ---

    # 3. Salvar no banco de dados (Inalterado)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (session_id, user_message, bot_response) VALUES (?, ?, ?)",
        (session_id, user_message, bot_response),
    )
    message_id = cursor.lastrowid
    conn.commit()
    conn.close()

    print(f"[Session: {session_id}] Respondido: {bot_response}")

    # 4. Retornar a resposta e o message_id (Inalterado)
    return jsonify({"response": bot_response, "message_id": message_id})


@app.route("/feedback", methods=["POST"])
def feedback():
    """Endpoint da API para salvar o feedback."""
    data = request.json
    message_id = data.get("message_id")
    rating = data.get("rating")  # 'like' ou 'dislike'

    if not message_id or not rating:
        return jsonify({"error": "Dados de feedback incompletos."}), 400

    print(f"Recebido feedback para message_id {message_id}: {rating}")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO feedback (message_id, rating) VALUES (?, ?)", (message_id, rating)
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Feedback recebido com sucesso."})


if __name__ == "__main__":
    os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)
    app.run(debug=True, host="0.0.0.0", port=5000)
