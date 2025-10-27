# Solução de Chatbot RAG com Gemini e Re-Ranking Avançado

Este projeto é uma aplicação web completa de um chatbot de Geração Aumentada por Recuperação (RAG). Ele permite que os usuários conversem sobre um conjunto de documentos PDF personalizados, fornecendo respostas precisas e contextuais.

A solução utiliza uma arquitetura moderna que combina um LLM de alta performance (Google Gemini), um banco de dados vetorial local (ChromaDB) e um pipeline de recuperação sofisticado de dois estágios (Recall + Re-ranking) para garantir a máxima relevância das respostas.

## Principais Funcionalidades

* **Ingestão de Dados Otimizada:** Processa arquivos PDF (`PyMuPDFLoader`), limpa o texto de rodapés usando Regex e divide os documentos em *chunks* otimizados.
* **Armazenamento Vetorial:** Utiliza o **ChromaDB** para criar e persistir um banco de dados de embeddings local.
* **Recuperação Híbrida (2-Estágios):**
    1.  **Recall (Busca Vetorial):** Encontra rapidamente os 20 documentos mais *similares* (Bi-Encoder).
    2.  **Precision (Re-Ranking):** Reavalia os 20 resultados usando um modelo **CrossEncoder** para encontrar os 3 documentos *semanticamente mais relevantes* para a pergunta.
* **Geração de Resposta:** Usa a API do **Google Gemini** (`gemini-1.5-flash`) para gerar respostas fluentes e precisas com base no contexto recuperado.
* **Interface Web:** Uma interface de chat simples e limpa construída com **Streamlit**.
* **Memória:** Armazena o histórico completo da conversa em um banco de dados **SQLite**.

## Arquitetura da Solução
| Componente                    | Tecnologia Utilizada     | Propósito                                               |
|-------------------------------|--------------------------|---------------------------------------------------------|
| **Gerenciamento de Ambiente** | Conda                    | Isolamento de dependências do projeto (`rag_solution`). |
| **Frontend**                  | Streamlit                | Interface do usuário (janela de chat).                  |
| **Backend**                   | Flask                    | Servidor web e API para o chat.                         |
| **LLM (Geração)**             | Google Gemini (via API)  | Geração de respostas.                                   |
| **Banco Vetorial**            | ChromaDB                 | Armazenamento de embeddings.                            |
| **Embeddings (Recall)**       | `all-MiniLM-L6-v2`       | Modelo Bi-Encoder para busca vetorial rápida.           |
| **Re-Ranking (Precision)**    | `ms-marco-MiniLM-L-6-v2` | Modelo Cross-Encoder para reclassificação de relevância.|
| **Banco de Dados (App)**      | SQLite                   | Armazenamento de histórico de chat e feedback.          |
| **Ingestão de PDF**           | PyMuPDFLoader            | Extração de texto otimizada de arquivos PDF.            |
| **Orquestração**              | LangChain                | O "motor" que conecta todos os componentes.             |

## 1. Instalação e Configuração

Siga estes passos para configurar e executar o ambiente.

### 1.1. Pré-requisitos

* **Python 3.10+** (Recomendado o uso de um ambiente virtual `venv` ou `conda`).
* **Chave de API do Google:** Você precisará de uma chave de API para o Gemini. Obtenha a sua no [Google AI Studio](https://aistudio.google.com/app/apikey).

### 1.2. Criação do Ambiente Virtual (Recomendado)

Abra seu terminal na pasta do projeto.

```bash
# 1. Crie o ambiente (ex: com venv)
python -m venv venv

# 2. Ative o ambiente
# Windows
.\venv\Scripts\activate
# macOS/Linux
source venv/bin/activate