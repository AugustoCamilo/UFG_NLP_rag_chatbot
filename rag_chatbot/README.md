# Solução de Chatbot RAG com Gemini e Re-Ranking Avançado

Este projeto é uma aplicação web completa de um chatbot de Geração Aumentada por Recuperação (RAG). Ele permite que os usuários conversem sobre um conjunto de documentos PDF personalizados, fornecendo respostas precisas e contextuais.

A solução utiliza uma arquitetura moderna que combina um LLM de alta performance (Google Gemini), um banco de dados vetorial local (ChromaDB) e um pipeline de recuperação sofisticado de dois estágios (Recall + Re-ranking) para garantir a máxima relevância das respostas.

## Principais Funcionalidades

  * **Ingestão de Dados Otimizada:** Processa arquivos PDF (`PyMuPDFLoader`), limpa o texto de rodapés e cabeçalhos usando Regex, e divide os documentos em *chunks* otimizados.
  * **Armazenamento Vetorial:** Utiliza o **ChromaDB** para criar e persistir um banco de dados de embeddings local.
  * **Recuperação Híbrida (2-Estágios):**
    1.  **Recall (Busca Vetorial):** Encontra rapidamente os 20 documentos mais *similares* (Bi-Encoder).
    2.  **Precision (Re-Ranking):** Reavalia os 20 resultados usando um modelo **CrossEncoder** para encontrar os 3 documentos *semanticamente mais relevantes* para a pergunta.
  * **Geração de Resposta:** Usa a API do **Google Gemini** (`gemini-1.5-flash`) para gerar respostas fluentes e precisas com base no contexto recuperado.
  * **Interface Web:** Uma interface de chat simples e limpa construída com **Flask**, HTML, CSS e JavaScript.
  * **Memória e Feedback:** Armazena o histórico completo da conversa e o feedback do usuário (curtir/não curtir) em um banco de dados **SQLite**.

## Arquitetura da Solução

| Componente                    | Tecnologia Utilizada     | Propósito                                               |
|-------------------------------|--------------------------|---------------------------------------------------------|
| **Gerenciamento de Ambiente** | Conda                    | Isolamento de dependências do projeto (`rag_solution`). |
| **Frontend**                  | HTML, CSS, JavaScript    | Interface do usuário (janela de chat).                  |
| **Backend**                   | Flask                    | Servidor web e API para o chat.                         |
| **LLM (Geração)**             | Google Gemini (via API)  | Geração de respostas.                                   |
| **Banco Vetorial**            | ChromaDB                 | Armazenamento de embeddings.                            |
| **Embeddings (Recall)**       | `all-MiniLM-L6-v2`       | Modelo Bi-Encoder para busca vetorial rápida.           |
| **Re-Ranking (Precision)**    | `ms-marco-MiniLM-L-6-v2` | Modelo Cross-Encoder para reclassificação de relevância.|
| **Banco de Dados (App)**      | SQLite                   | Armazenamento de histórico de chat e feedback.          |
| **Ingestão de PDF**           | PyMuPDFLoader            | Extração de texto otimizada de arquivos PDF.            |
| **Orquestração**              | LangChain                | O "motor" que conecta todos os componentes.             |

## 1\. Instalação e Configuração

Siga estes passos para configurar e executar o ambiente.

### 1.1. Pré-requisitos

  * **Anaconda (ou Miniconda):** Recomendado para gerenciamento de ambiente.
  * **Chave de API do Google:** Você precisará de uma chave de API para o Gemini. Obtenha a sua no [Google AI Studio](https://aistudio.google.com/app/apikey).

### 1.2. Criação do Ambiente Conda

Abra o **Anaconda Prompt** e crie um ambiente Python 3.10 dedicado.

```bash
conda create -n rag_solution python=3.12.7 -y
conda activate rag_solution
```

### 1.3. Instalação das Dependências

Todas as dependências do projeto estão listadas no arquivo `requirements.txt`.

```bash
pip install -r requirements.txt
```

#### ⚠️ Solução de Problemas (Opcional)

Durante a instalação, o `pip` pode exibir um aviso sobre o `aext-assistant-server` (um pacote interno do Anaconda). Se isso ocorrer, você pode corrigi-lo executando:

```bash
conda install anaconda-cloud-auth
```

### 1.4. Configuração da Chave de API

Você deve fornecer sua chave de API do Gemini para que a aplicação possa se conectar ao Google.

1.  Na pasta raiz do projeto (`rag_chatbot/`), crie um novo arquivo chamado `.env`.

2.  Abra este arquivo e adicione sua chave:

    ```ini
    # .env
    # Substitua "SUA_CHAVE_AQUI" pela sua chave de API do Google AI Studio
    GEMINI_API_KEY="SUA_CHAVE_AQUI"
    ```

O arquivo `config.py` carregará automaticamente esta chave.

## 2\. Como Executar a Solução

Siga esta sequência para iniciar a aplicação:

### Passo 1: Adicionar Documentos

Coloque todos os arquivos `.pdf` que você deseja que o chatbot utilize dentro da pasta `/docs`.

### Passo 2: Criar o Banco de Dados do Aplicativo

Este comando executa o script `database.py`, que criará a pasta `/database` e o arquivo `chat_solution.db` dentro dela.

```bash
python database.py
```

*(Você só precisa executar este comando uma vez.)*

### Passo 3: Ingerir os Documentos (Criar Embeddings)

Este é o passo mais importante. Ele irá ler seus PDFs, limpá-los, dividi-los e criar o banco de dados vetorial na pasta `/vector_db`.

```bash
python ingest.py
```

*(**Nota:** Execute este script sempre que você adicionar, remover ou modificar os arquivos PDF na pasta `/docs`.)*

### Passo 4: Iniciar o Servidor Web

Este comando inicia o servidor Flask, que carregará os modelos de IA (Embeddings, Re-Ranker e Gemini) e servirá a interface do chat.

```bash
python app.py
```

Aguarde o terminal carregar todos os modelos. Quando estiver pronto, você verá uma mensagem indicando que o servidor está rodando, similar a:

```
...
Modelo de Re-Ranking carregado.
Carregando LLM (Gemini Model: gemini-1.5-flash)...
Cadeia RAG pronta.
 * Running on http://127.0.0.1:5000
```

### Passo 5: Acessar o Chatbot

Abra seu navegador e acesse a interface da aplicação:

🔗 **[http://127.0.0.1:5000](https://www.google.com/url?sa=E&source=gmail&q=http://127.0.0.1:5000)**

## 3\. Ferramentas de Validação

O projeto inclui um script de linha de comando para testar e validar o banco de dados vetorial sem precisar iniciar a aplicação web.

### `read_db.py`

Execute este script para interagir diretamente com o seu `vector_db` e a lógica de Re-Ranking.

```bash
python read_db.py
```

Após carregar, ele oferece um prompt interativo com os seguintes comandos:

  * **`<sua pergunta>`:** Digite uma pergunta para ver os 3 chunks mais relevantes que o Re-Ranker encontrou.
  * **`!todos`:** Lista o conteúdo parcial de *todos* os chunks armazenados no banco.
  * **`!exportar`:** Salva o conteúdo completo de todos os chunks e seus metadados em um arquivo `chunks_exportados.xml` na pasta raiz.
  * **`!sair`:** Encerra o script.

## Estrutura do Projeto

```
/rag_chatbot
|
|-- .env                     # (Você cria) Armazena segredos (GEMINI_API_KEY)
|-- config.py                # Arquivo de configuração central (caminhos, nomes de modelos)
|-- requirements.txt         # Lista de todas as dependências Python
|
|-- app.py                   # Aplicação principal (Servidor Flask)
|-- rag_core.py              # Lógica principal do RAG (Cadeia LangChain, Re-Ranker)
|-- database.py              # Script para inicializar o banco de dados SQLite
|
|-- ingest.py                # Script para processar PDFs e criar o banco de vetores
|-- read_db.py               # Ferramenta CLI para validar o banco de vetores
|
|-- /docs/                   # Pasta para colocar seus arquivos .pdf
|-- /database/               # Pasta onde o banco SQLite (histórico) é salvo
|-- /vector_db/              # Pasta onde o ChromaDB (vetores) é salvo
|
|-- /static/
|   |-- style.css            # Estilos da interface
|   |-- script.js            # Lógica do frontend (chat, feedback)
|
|-- /templates/
|   |-- index.html           # Estrutura HTML da página de chat
|
|-- README.md                # Este arquivo
```