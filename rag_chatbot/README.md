# Solução de Chatbot RAG com Gemini, Re-Ranking Avançado e Ferramentas de Auditoria

Este projeto implementa uma aplicação web completa de um chatbot baseado em Geração Aumentada por Recuperação (RAG). Ele permite que os usuários conversem sobre um conjunto de documentos PDF personalizados, fornecendo respostas contextuais e precisas, com a capacidade de coletar feedback sobre as respostas geradas.

A solução utiliza uma arquitetura moderna que combina:
* Um LLM de alta performance (Google Gemini).
* Um banco de dados vetorial local (ChromaDB) para armazenamento eficiente de embeddings.
* Um pipeline de recuperação sofisticado de dois estágios (Recall + Re-ranking) para maximizar a relevância do contexto recuperado.
* Um banco de dados SQLite para persistir o histórico das conversas e o feedback dos usuários.
* Ferramentas web dedicadas para auditoria e validação da base vetorial e do histórico de chat.

## Principais Funcionalidades

* **Ingestão de Dados Otimizada:**
    * Processa arquivos PDF usando `PyMuPDFLoader`.
    * Limpa automaticamente rodapés comuns usando Expressões Regulares (Regex) durante a ingestão.
    * Divide os documentos limpos em *chunks* (pedaços) otimizados usando `RecursiveCharacterTextSplitter`.
* **Armazenamento Vetorial:**
    * Utiliza o **ChromaDB** para criar e persistir um banco de dados de embeddings localmente.
* **Recuperação Híbrida (2-Estágios):**
    1.  **Recall (Busca Vetorial Rápida):** Usa um modelo Bi-Encoder (`all-MiniLM-L6-v2`) para encontrar rapidamente os `SEARCH_K_RAW` (padrão 20) documentos semanticamente mais *similares* à pergunta do usuário.
    2.  **Precision (Re-Ranking Inteligente):** Reavalia os resultados do Recall usando um modelo CrossEncoder (`cross-encoder/ms-marco-MiniLM-L6-v2`) para reordená-los com base na relevância semântica e selecionar os `SEARCH_K_FINAL` (padrão 3) documentos mais relevantes para a pergunta.
* **Geração de Resposta:**
    * Utiliza a API do **Google Gemini** (configurável, padrão `gemini-1.5-flash`) para gerar respostas fluentes e precisas, baseando-se *exclusivamente* no contexto recuperado e no histórico da conversa.
    * Implementa um *system prompt* detalhado com persona, restrições de conhecimento e regras situacionais (saudações, resposta não encontrada).
* **Interface Web:**
    * Interface de chat amigável construída com **Streamlit** (`app.py`).
    * Foco automático na caixa de entrada de texto para melhor usabilidade.
    * Barra lateral com botão para encerrar a aplicação.
* **Memória e Feedback:**
    * Armazena o histórico completo da conversa (incluindo timestamps detalhados, contagem de tokens/caracteres e métricas de duração) em um banco de dados **SQLite** (`database/chat_solution.db`).
    * Permite que os usuários avaliem as respostas do bot (👍/👎).
    * Armazena o feedback na tabela `feedback` do banco SQLite.
    * Exibe uma mensagem de agradecimento (`st.toast`) após o feedback.
* **Ferramentas de Auditoria:**
    * **`validate_vector_db.py`:** Interface web (Streamlit) para validar a base de vetores ChromaDB. Permite testar a busca com re-ranking, listar todos os chunks e exportá-los para XML.
    * **`validate_history_db.py`:** Interface web (Streamlit) para auditar o histórico de chat do SQLite. Permite listar sessões, buscar conversas por ID, visualizar o histórico completo, visualizar feedbacks e exportar o histórico para CSV.

## Arquitetura da Solução

* **Interface Web (Frontend/Backend):**
    * **Tecnologia:** Streamlit
    * **Versão:** `1.50.0`
    * **Propósito:** Interface do usuário (janela de chat) e das Ferramentas de Auditoria.
    * **Arquivo(s):** `app.py`, `validate_vector_db.py`, `validate_history_db.py`
* **Orquestração RAG:**
    * **Tecnologia:** LangChain / LangGraph
    * **Versão:** `1.0.2` / `1.0.1`
    * **Propósito:** Conecta os componentes do pipeline RAG (Retrieval -> Generation).
    * **Arquivo(s):** `rag_chain.py`
* **LLM (Geração):**
    * **Tecnologia:** Google Gemini (via `langchain-google-genai`)
    * **Versão:** `3.0.0`
    * **Propósito:** Geração das respostas do chatbot.
    * **Arquivo(s):** `rag_chain.py`, `config.py`
* **Banco Vetorial:**
    * **Tecnologia:** ChromaDB (via `langchain-chroma`)
    * **Versão:** `1.0.0`
    * **Propósito:** Armazenamento local e persistente dos embeddings dos chunks.
    * **Arquivo(s):** `ingest.py`, `vector_retriever.py`, `config.py`
* **Embeddings (Recall):**
    * **Tecnologia:** `sentence-transformers` / `all-MiniLM-L6-v2`
    * **Versão:** `5.1.2`
    * **Propósito:** Modelo Bi-Encoder para criar vetores e realizar a busca inicial rápida.
    * **Arquivo(s):** `ingest.py`, `vector_retriever.py`, `config.py`
* **Re-Ranking (Precision):**
    * **Tecnologia:** `sentence-transformers` / `cross-encoder/ms-marco-MiniLM-L6-v2`
    * **Versão:** `5.1.2`
    * **Propósito:** Modelo CrossEncoder para reordenar resultados com base na relevância.
    * **Arquivo(s):** `vector_retriever.py`, `config.py`
* **Banco de Dados (App):**
    * **Tecnologia:** SQLite
    * **Versão:** (Nativo do Python)
    * **Propósito:** Armazenamento do histórico de chat, métricas e feedback.
    * **Arquivo(s):** `database.py`, `rag_chain.py`, `validate_history_db.py`
* **Ingestão de PDF:**
    * **Tecnologia:** `PyMuPDF` (via `langchain`)
    * **Versão:** `1.26.5`
    * **Propósito:** Extração eficiente de texto de arquivos PDF.
    * **Arquivo(s):** `ingest.py`
* **Divisão de Texto:**
    * **Tecnologia:** `langchain-text-splitters`
    * **Versão:** `1.0.0`
    * **Propósito:** Fragmentação do texto extraído em chunks.
    * **Arquivo(s):** `ingest.py`
* **Utilitários:**
    * **Tecnologia:** `python-dotenv`, `tqdm`
    * **Versão:** `1.1.1`, `4.67.1`
    * **Propósito:** Carregamento de variáveis de ambiente, barras de progresso.
    * **Arquivo(s):** Diversos

## 1. Instalação e Configuração

Siga estes passos para configurar o ambiente e executar a solução.

### 1.1. Pré-requisitos

* **Python 3.10+** (Recomendado o uso de um ambiente virtual `venv` ou `conda`).
* **Chave de API do Google:** Necessária para usar o modelo Gemini. Obtenha a sua no [Google AI Studio](https://aistudio.google.com/app/apikey).

### 1.2. Criação do Ambiente Virtual (Recomendado)

Abra seu terminal na pasta raiz do projeto.

```bash
# Exemplo usando venv (substitua por conda se preferir)
# 1. Crie o ambiente
python -m venv venv

# 2. Ative o ambiente
# Windows
.\venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
````

### 1.3. Instalação das Dependências

Com o ambiente virtual ativo, instale todas as bibliotecas listadas no `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 1.4. Configuração da Chave de API

1.  Na pasta raiz do projeto, crie um arquivo chamado `.env`.

2.  Adicione sua chave de API do Google Gemini a este arquivo:

    ```ini
    # .env
    # Substitua "SUA_CHAVE_AQUI" pela sua chave de API
    GEMINI_API_KEY="SUA_CHAVE_AQUI"
    ```

    O arquivo `config.py` carregará esta chave automaticamente.

## 2\. Como Executar a Solução

Siga a sequência abaixo para preparar e iniciar o chatbot.

### Passo 1: Adicionar Documentos

Coloque os arquivos `.pdf` que servirão como base de conhecimento dentro da pasta `/docs`.

### Passo 2: Inicializar o Banco de Dados do Histórico

Execute este comando **uma única vez** para criar a pasta `/database` e o arquivo `chat_solution.db` com as tabelas `chat_history` e `feedback`.

```bash
python database.py
```

**(Importante:** Se você alterar a estrutura das tabelas no `database.py` no futuro, precisará excluir o arquivo `chat_solution.db` e executar este comando novamente).

### Passo 3: Ingerir os Documentos (Criar/Atualizar Banco Vetorial)

Este script processa os PDFs da pasta `/docs`, limpa os rodapés, divide em chunks, gera os embeddings e salva/sobrescreve o banco de dados vetorial na pasta `/vector_db`.

```bash
python ingest.py
```

**(Importante:** Execute este script sempre que adicionar, remover ou modificar os arquivos PDF na pasta `/docs`.)

### Passo 4: Iniciar a Aplicação do Chatbot

Este comando inicia o servidor Streamlit para a interface principal do chatbot.

```bash
streamlit run app.py
```

Aguarde o carregamento dos modelos. O aplicativo será aberto automaticamente no seu navegador ou fornecerá um URL (geralmente `http://localhost:8501`).

## 3\. Ferramentas de Auditoria (Web)

O projeto inclui duas interfaces web (Streamlit) dedicadas para validação e auditoria dos bancos de dados. Execute-as em terminais separados conforme necessário.

### 3.1. `validate_vector_db.py`: Auditoria da Base Vetorial

Esta ferramenta permite inspecionar o conteúdo e o desempenho da base de vetores (ChromaDB) criada pelo `ingest.py`.

**Como Executar:**

```bash
streamlit run validate_vector_db.py
```

**Funcionalidades:**

  * **Testar Busca (Re-Ranking):** Insira uma consulta e veja os chunks mais relevantes recuperados pelo `vector_retriever`, incluindo os scores de relevância.
  * **Listar Todos os Chunks:** Exibe o início do conteúdo de todos os chunks armazenados no banco.
  * **Exportar Chunks para XML:** Gera um arquivo `chunks_exportados.xml` na pasta raiz com o conteúdo completo e metadados de todos os chunks.
  * **Encerrar Servidor:** Botão para parar a execução desta ferramenta de validação.

### 3.2. `validate_history_db.py`: Auditoria do Histórico de Chat

Esta ferramenta permite consultar e analisar o histórico de conversas e feedbacks armazenados no banco de dados SQLite (`chat_solution.db`).

**Como Executar:**

```bash
streamlit run validate_history_db.py
```

**Funcionalidades:**

  * **Listar Todas as Sessões:** Mostra um resumo de todas as conversas (sessões), incluindo contagem de mensagens, duração média e última atividade.
  * **Buscar por Sessão:** Permite visualizar a transcrição completa de uma conversa específica, fornecendo o ID da Sessão.
  * **Ver Histórico Completo:** Exibe todas as mensagens de todas as sessões (pode ser lento para bancos grandes).
  * **Ver Avaliações (Feedback):** Lista todos os feedbacks (👍/👎) dados pelos usuários, mostrando a mensagem associada.
  * **Exportar Histórico para CSV:** Gera um arquivo `historico_chat_exportado.csv` na pasta raiz com todos os dados da tabela `chat_history`.
  * **Encerrar Servidor:** Botão para parar a execução desta ferramenta de auditoria.

## Estrutura do Projeto

```
/rag_chatbot
|
|-- .env                     # (Você cria) Armazena a GEMINI_API_KEY
|-- config.py                # Configurações centrais (caminhos, nomes de modelos, etc.)
|-- requirements.txt         # Dependências Python (com versões fixadas)
|
|-- app.py                   # Aplicação principal do Chatbot (Streamlit UI)
|-- rag_chain.py             # Lógica principal do RAG (LangGraph, LLM, Histórico, Feedback)
|-- vector_retriever.py      # Classe para busca vetorial e re-ranking (Chroma + CrossEncoder)
|-- database.py              # Gerenciamento do schema do banco de dados SQLite (histórico/feedback)
|
|-- ingest.py                # Script para processar PDFs e criar/atualizar o VectorDB (Chroma)
|
|-- validate_vector_db.py    # Ferramenta de Auditoria Web para o VectorDB (Streamlit UI)
|-- validate_history_db.py   # Ferramenta de Auditoria Web para o Histórico/Feedback (Streamlit UI)
|
|-- /docs/                   # Pasta para colocar os arquivos .pdf de entrada
|-- /database/               # Pasta onde o banco SQLite (chat_solution.db) é salvo
|   |-- chat_solution.db     # Arquivo do banco SQLite
|-- /vector_db/              # Pasta onde o ChromaDB (embeddings) é salvo
|
|-- README.md                # Este arquivo
|-- chunks_exportados.xml    # (Gerado por validate_vector_db.py) Exportação dos chunks
|-- historico_chat_exportado.csv # (Gerado por validate_history_db.py) Exportação do histórico
```

```
```