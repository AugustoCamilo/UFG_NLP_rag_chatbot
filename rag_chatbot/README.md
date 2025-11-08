# Solução de Chatbot RAG com Gemini, Re-Ranking Avançado e Suíte de Avaliação de Métricas

Este projeto implementa uma aplicação web completa de um chatbot RAG (Geração Aumentada por Recuperação). Ele permite que os usuários conversem sobre um conjunto de documentos PDF personalizados, fornecendo respostas contextuais e precisas, com a capacidade de coletar feedback sobre as respostas geradas.

O diferencial desta solução é a sua **Suíte de Avaliação e Auditoria**, um conjunto de ferramentas web dedicadas que permitem a uma equipe de avaliadores testar, medir (com métricas como **Hit Rate**, **MRR** e **Precisão@K**), e consolidar relatórios de performance (via Import/Export XML), criando um ciclo de melhoria contínua (CI/CD) para a qualidade do RAG.

A solução utiliza uma arquitetura moderna que combina:

  * Um LLM de alta performance (Google Gemini).
  * Um banco de dados vetorial local (ChromaDB) para armazenamento de embeddings.
  * Um pipeline de recuperação sofisticado de dois estágios (Recall + Re-ranking) para maximizar a relevância.
  * Um banco de dados SQLite para persistir o histórico das conversas, feedbacks e **dados de avaliação de métricas**.

## Principais Funcionalidades

  * **Ingestão de Dados Otimizada:** Processa arquivos PDF (`PyMuPDFLoader`), limpa rodapés customizáveis (Regex) e divide em *chunks* otimizados (`RecursiveCharacterTextSplitter`).
  * **Armazenamento Vetorial:** Utiliza o **ChromaDB** para criar e persistir um banco de dados de embeddings localmente.
  * **Recuperação Híbrida (2-Estágios):**
    1.  **Recall (Busca Vetorial Rápida):** Usa um modelo Bi-Encoder (`all-MiniLM-L6-v2`) para encontrar rapidamente os `SEARCH_K_RAW` (padrão 20) documentos semanticamente similares.
    2.  **Precision (Re-Ranking Inteligente):** Reavalia os resultados do Recall usando um modelo CrossEncoder (`cross-encoder/ms-marco-MiniLM-L6-v2`) para reordená-los com base na relevância e selecionar os `SEARCH_K_FINAL` (padrão 3) documentos mais relevantes.
  * **Geração de Resposta:** Utiliza a API do **Google Gemini** para gerar respostas fluentes, baseando-se no contexto recuperado e no histórico da conversa.
  * **Interface Web (`app.py`):** Interface de chat principal para o usuário final, construída com **Streamlit**.
  * **Memória e Feedback:** Armazena o histórico completo da conversa (incluindo métricas de performance e tokens) e o feedback do usuário (👍/👎) no banco **SQLite**.

### Suíte de Avaliação e Auditoria

O sistema inclui três aplicações web independentes para validação e auditoria:

1.  **`validate_vector_db.py` (Coleta de Avaliação):**

      * Uma interface para o "Avaliador Humano" testar a performance do retriever (Modo Vetorial vs. Modo Re-Ranking).
      * O avaliador marca os chunks relevantes (para Hit Rate/Precisão) e o melhor chunk (para MRR).
      * **Salva** os resultados da avaliação (queries, chunks, scores, e métricas calculadas) no banco de dados SQLite (`validation_runs`, `validation_retrieved_chunks`).

2.  **`validate_evaluation.py` (Dashboard de Métricas):**

      * A ferramenta central de *análise* que **lê** os dados de avaliação salvos.
      * **Resumo de Métricas:** Apresenta um dashboard que compara `vector_only` vs. `reranked` lado a lado, com as médias de **Hit Rate**, **MRR** e **Precisão@K**.
      * **Lista Detalhada:** Permite ver cada rodada de teste individualmente, com suas métricas e chunks.
      * **Exportar/Importar XML:** Permite que equipes exportem seus resultados de avaliação e importem os resultados de colegas, consolidando os dados. O sistema ignora duplicatas automaticamente durante a importação (baseado no timestamp).

3.  **`validate_history_db.py` (Auditoria de Produção):**

      * Um dashboard de "BI" que **lê** o histórico de uso do `app.py` (tabelas `chat_history` e `feedback`).
      * Permite listar todas as sessões, ver transcrições completas e auditar o feedback (👍/👎) dado pelos usuários finais.

-----

## Arquitetura e Fluxo de Dados

O sistema é modular, com dependências claras entre os scripts.

### 1\. Componentes Principais (Produção)

  * **`app.py` (Frontend)**
      * Renderiza a UI do chat e gerencia o `session_id`.
      * Depende de: `rag_chain.py` (para gerar respostas e salvar feedback).
  * **`rag_chain.py` (Backend Lógico)**
      * Orquestra o fluxo RAG (histórico, recuperação, geração) usando LangGraph.
      * Depende de: `vector_retriever.py` (para buscar contexto), `database.py` (para ler/escrever histórico e feedback), `config.py` (para o LLM).
  * **`vector_retriever.py` (Módulo de Recuperação)**
      * Implementa a lógica de Recall (Chroma) e Re-Ranking (CrossEncoder).
      * Depende de: `config.py` (para nomes de modelos e parâmetros K), `/vector_db` (para ler o ChromaDB).
  * **`database.py` (Schema do Banco)**
      * Define a estrutura de *todas* as tabelas do SQLite (Produção e Avaliação).
      * Depende de: `sqlite3`.
  * **`config.py` (Configuração)**
      * Centraliza todos os caminhos, chaves de API e nomes de modelos.
      * Não tem dependências de outros módulos do projeto.

### 2\. Scripts de Ingestão e Ferramentas

  * **`ingest.py` (Ingestão)**
      * Script de linha de comando para popular o banco de vetores.
      * Depende de: `config.py` (para caminhos e modelos), `/docs` (lê PDFs), `/vector_db` (escreve/sobrescreve o ChromaDB).
  * **`validate_vector_db.py` (Coleta de Avaliação)**
      * App Streamlit para *escrever* dados de avaliação.
      * Depende de: `vector_retriever.py` (para rodar as buscas) e `database.py` (para salvar os resultados).
  * **`validate_evaluation.py` (Dashboard de Métricas)**
      * App Streamlit para *ler, analisar, exportar e importar* dados de avaliação.
      * Depende de: `database.py` (para ler/escrever na tabela `validation_runs`).
  * **`validate_history_db.py` (Auditoria de Produção)**
      * App Streamlit para *ler* o histórico de produção.
      * Depende de: `database.py` (para ler as tabelas `chat_history` e `feedback`).

-----

## Tecnologias e Dependências

A solução utiliza as seguintes bibliotecas, conforme definido no `requirements.txt`:

```
# Framework da Interface Web
streamlit==1.50.0

# Frameworks principais do LangChain
langchain==1.0.2
langchain-core==1.0.1
langgraph==1.0.1

# Módulos e integrações do LangChain
langchain-community==0.4
langchain-chroma==1.0.0
langchain-google-genai==3.0.0
langchain-huggingface==1.0.0
langchain-text-splitters==1.0.0

# Modelos de Embedding e Re-Ranking
sentence-transformers==5.1.2

# Carregamento de PDF (requerido pelo PyMuPDFLoader)
PyMuPDF==1.26.5

# Utilitários
python-dotenv==1.1.1
tqdm==4.67.1
```

-----

## 1\. Instalação e Configuração

Siga estes passos para configurar o ambiente e executar a solução.

### 1.1. Pré-requisitos

  * **Python 3.10+** (Recomendado o uso de um ambiente virtual `venv` ou `conda`).
  * **Chave de API do Google:** Necessária para usar o modelo Gemini. Obtenha a sua no [Google AI Studio](https://aistudio.google.com/app/apikey).

### 1.2. Criação do Ambiente Virtual (Recomendado)

Abra seu terminal na pasta raiz do projeto. Escolha a opção (`venv` ou `conda`) de sua preferência.

-----

**Opção A: Usando `venv` (Padrão do Python)**

```bash
# 1. Crie o ambiente (usando o nome 'rag_solution')
python -m venv rag_solution

# 2. Ative o ambiente
# Windows
.\rag_solution\Scripts\activate
# macOS/Linux
source rag_solution/bin/activate
```

-----

**Opção B: Usando `conda` (Anaconda)**

```bash
# 1. Crie o ambiente (usando o nome 'rag_solution' e especificando Python 3.10+)
conda create -n rag_solution python=3.10

# 2. Ative o ambiente
conda activate rag_solution
```

### 1.3. Instalação das Dependências

Com o ambiente virtual (`rag_solution`) ativo, instale todas as bibliotecas listadas no `requirements.txt`:

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

-----

## 2\. Como Executar a Solução (Produção)

Siga a sequência abaixo para preparar e iniciar o chatbot principal.

### Passo 1: Adicionar Documentos

Coloque os arquivos `.pdf` que servirão como base de conhecimento dentro da pasta `/docs`.

### Passo 2: Inicializar o Banco de Dados do Histórico

Execute este comando **uma única vez** para criar a pasta `/database` e o arquivo `chat_solution.db` com todas as tabelas (produção e avaliação).

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

Aguarde o carregamento dos modelos. O aplicativo será aberto automaticamente no seu navegador (geralmente `http://localhost:8501`).

-----

## 3\. Suíte de Avaliação e Auditoria (Execução)

O projeto inclui três aplicações web (Streamlit) dedicadas para validação e auditoria. Execute-as em terminais separados conforme necessário.

### 3.1. `validate_vector_db.py`: Coleta de Avaliação Manual

Esta ferramenta permite **criar** os dados de avaliação. Você testa queries, avalia os resultados (marcando checkboxes e radio buttons) e salva as métricas no banco de dados.

**Como Executar:**

```bash
streamlit run validate_vector_db.py
```

**Funcionalidades:**

  * **Testar Busca (SÓ Vetorial):** Testa a busca vetorial pura.
  * **Testar Busca (COM Re-Ranking):** Testa o pipeline completo com re-ranking.
  * **Formulário de Avaliação:** Permite ao avaliador calcular HR, MRR e P@K para cada query.
  * **Listar/Exportar Chunks:** Ferramentas de utilidade para inspecionar o ChromaDB.

### 3.2. `validate_evaluation.py`: Dashboard de Métricas de Avaliação

Esta ferramenta permite **analisar** os dados coletados pela ferramenta anterior. É o seu principal dashboard para medir a performance do RAG.

**Como Executar:**

```bash
streamlit run validate_evaluation.py
```

**Funcionalidades:**

  * **Resumo das Métricas:** Compara o desempenho (HR, MRR, P@K) de "Vetorial" vs. "Re-Ranking".
  * **Listar Avaliações Detalhada:** Permite ver cada teste individual que foi salvo.
  * **Exportar Avaliações (XML):** Cria um backup ou arquivo de compartilhamento com todos os dados de avaliação.
  * **Importar Avaliações (XML):** Permite consolidar dados de avaliação de outros membros da equipe, ignorando duplicatas.

### 3.3. `validate_history_db.py`: Dashboard de Auditoria de Produção

Esta ferramenta permite analisar o **uso real** do seu chatbot (`app.py`), lendo o histórico de produção.

**Como Executar:**

```bash
streamlit run validate_history_db.py
```

**Funcionalidades:**

  * **Listar Todas as Sessões:** Mostra um resumo de todas as conversas (sessões).
  * **Buscar por Sessão:** Permite visualizar a transcrição completa de uma conversa específica.
  * **Ver Avaliações (Feedback):** Lista todos os feedbacks (👍/👎) dados pelos usuários finais, mostrando a mensagem associada.
  * **Exportar Histórico para CSV:** Gera um arquivo CSV com todos os dados da tabela `chat_history`.

-----

## 4\. Fluxo de Trabalho: Coletando Métricas (Criando o Gabarito)

A parte mais importante da avaliação de um RAG é a criação de um "gabarito" (dataset de *ground truth*) de alta qualidade. Este gabarito consiste em um conjunto de perguntas-padrão (queries) e o julgamento humano sobre os resultados que o sistema retorna para elas.

O dashboard `validate_evaluation.py` só é útil após a coleta desses dados, que é feita com o `validate_vector_db.py`.

### Procedimento de Coleta

Para construir um gabarito robusto para comparar "Vetorial" vs. "Re-Ranking", o avaliador humano deve seguir estes passos:

1.  **Executar a Ferramenta:** Inicie a ferramenta de coleta de avaliação.
    ```bash
    streamlit run validate_vector_db.py
    ```
2.  **Preparar a Query:** Tenha uma pergunta de teste em mente (ex: "Quais os descontos para pagamento à vista?").
3.  **Testar o Modo 1 (Vetorial):** Selecione "Testar Busca (SÓ Vetorial)" e execute a busca. O sistema exibirá os **K\_FINAL** (ex: 3) resultados da busca vetorial pura.
4.  **Realizar o Julgamento (Gabarito):**
      * **Checkboxes (Hit Rate / Precisão@K):** O avaliador deve ler a query e marcar *todos* os chunks que, em sua opinião, são relevantes para responder à pergunta.
      * **Radio Buttons (MRR):** O avaliador deve selecionar o *único e melhor* chunk que responde à pergunta. Se nenhum for bom, deve selecionar "Nenhuma (MRR = 0)".
5.  **Salvar a Avaliação:** Clique em "Salvar Avaliação". O sistema irá calcular as três métricas (HR, MRR, P@K) com base nos seus cliques e salvará essa rodada no banco de dados.
6.  **Testar o Modo 2 (Re-Ranking):** Selecione "Testar Busca (COM Re-Ranking)". Insira a **mesma query** do Passo 2. O sistema exibirá os K\_FINAL resultados *após* o processo de re-ranking.
7.  **Realizar o Julgamento (Gabarito):** Repita o Passo 4, julgando este novo conjunto de resultados.
8.  **Salvar a Avaliação:** Clique em "Salvar Avaliação" novamente.
9.  **Repetir:** Volte ao Passo 2 com uma nova pergunta.

Ao repetir esse processo para dezenas de queries, você construirá um dataset rico que permitirá ao `validate_evaluation.py` calcular estatisticamente qual dos dois métodos é superior.

### Exemplos de Cálculo de Métricas (K=3)

Assuma que o sistema está configurado para retornar **K=3** resultados.

-----

**Exemplo 1: Resultado "Perfeito"**

  * **Query:** "O que é transação tributária?"
  * **Resultados:** O sistema retorna 3 chunks.
  * **Julgamento do Avaliador:**
      * **Checkboxes:** Chunk 1 (define o termo) e Chunk 3 (dá um exemplo) são marcados como relevantes.
      * **Radio:** O Chunk 1 é selecionado como a "MELHOR" resposta.
  * **Métricas Salvas:**
      * `hit_rate_eval` = **1** (porque *pelo menos um* foi marcado)
      * `mrr_eval` = **1.0** (porque o melhor estava na posição 1; `1/1`)
      * `precision_at_k_eval` = **0.66** (porque *dois* foram marcados; `2/3`)

-----

**Exemplo 2: Resultado "Bom, mas Mal Ranqueado"**

  * **Query:** "Quais os descontos para pagamento à vista?"
  * **Resultados:** O sistema retorna 3 chunks. O Chunk 1 fala sobre parcelamento, o Chunk 2 fala sobre juros, e o Chunk 3 fala sobre desconto à vista.
  * **Julgamento do Avaliador:**
      * **Checkboxes:** Apenas o Chunk 3 é marcado como relevante.
      * **Radio:** O Chunk 3 é selecionado como a "MELHOR" resposta.
  * **Métricas Salvas:**
      * `hit_rate_eval` = **1** (porque *pelo menos um* foi marcado)
      * `mrr_eval` = **0.33** (porque o melhor estava na posição 3; `1/3`)
      * `precision_at_k_eval` = **0.33** (porque *um* foi marcado; `1/3`)

-----

**Exemplo 3: Resultado "Falha Total (Miss)"**

  * **Query:** "Qual o CNPJ da Procuradoria?" (Assumindo que esta informação não está nos documentos)
  * **Resultados:** O sistema retorna 3 chunks que mencionam "Procuradoria", mas nenhum contém o CNPJ.
  * **Julgamento do Avaliador:**
      * **Checkboxes:** Nenhum chunk é marcado.
      * **Radio:** A opção "Nenhuma (MRR = 0)" é selecionada.
  * **Métricas Salvas:**
      * `hit_rate_eval` = **0** (porque *nenhum* foi marcado)
      * `mrr_eval` = **0.0** (porque "Nenhuma" foi selecionada)
      * `precision_at_k_eval` = **0.0** (porque *zero* foram marcados; `0/3`)

-----

## 5\. Estrutura do Projeto

```
/rag_chatbot
|
|-- .env                     # (Você cria) Armazena a GEMINI_API_KEY
|-- config.py                # Configurações centrais (caminhos, nomes de modelos, etc.)
|-- requirements.txt         # Dependências Python
|
|-- app.py                   # Aplicação principal do Chatbot (Streamlit UI)
|-- rag_chain.py             # Lógica principal do RAG (LangGraph, LLM, Histórico)
|-- vector_retriever.py      # Classe para busca vetorial e re-ranking (Chroma + CrossEncoder)
|-- database.py              # Gerenciamento do schema do banco de dados SQLite (todas as tabelas)
|
|-- ingest.py                # Script para processar PDFs e criar/atualizar o VectorDB (Chroma)
|
|-- validate_vector_db.py    # Ferramenta de Coleta de Avaliação (Streamlit UI)
|-- validate_evaluation.py   # Ferramenta de Análise de Métricas (Streamlit UI)
|-- validate_history_db.py   # Ferramenta de Auditoria de Produção (Streamlit UI)
|
|-- /docs/                   # Pasta para colocar os arquivos .pdf de entrada
|-- /database/               # Pasta onde o banco SQLite (chat_solution.db) é salvo
|   |-- chat_solution.db     # Arquivo do banco SQLite
|-- /vector_db/              # Pasta onde o ChromaDB (embeddings) é salvo
|
|-- README.md                # Este arquivo
```

-----

## 6\. Nota sobre o Desenvolvimento e Colaboração com IA

Este projeto representa um fluxo de trabalho moderno de desenvolvimento assistido por Inteligência Artificial.

A arquitetura do sistema, a definição de todas as regras de negócio, os requisitos funcionais, o fluxo de dados e o processo de depuração e validação (QA) foram concebidos e dirigidos pelo desenvolvedor humano.

A geração da sintaxe de código (Python, Streamlit, SQL, etc.), a documentação inicial (*docstrings*) e as refatorações de código foram executadas em colaboração direta com o **Google Gemini**, que atuou como um assistente de programação (*pair programmer*). O fluxo de trabalho consistiu no desenvolvedor solicitando as funcionalidades em linguagem natural e, em seguida, validando, testando e corrigindo o código gerado pelo LLM.