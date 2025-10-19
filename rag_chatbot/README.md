# Configuração do Ambiente Anaconda

## 1. Criação do Ambiente Conda

Primeiro, vamos criar um ambiente Conda dedicado para isolar o projeto.

Abra o terminal **Anaconda Prompt** e execute os seguintes comandos:

```bash
conda create -n rag_solution python=3.10 -y
conda activate rag_solution
```

## 2. Instalação das Dependências

Instale os pacotes necessários usando `pip`. A biblioteca `llama-cpp-python` pode exigir etapas de compilação, mas geralmente funciona bem via pip na maioria dos sistemas.

### Instalação principal:

```bash
pip install langchain langchain-community flask chromadb sentence-transformers pypdf
```

### Para o LLM local:

Isso compilará o modelo para sua CPU (ou GPU, se configurado). Pode demorar alguns minutos.

```bash
pip install llama-cpp-python
```

### Instalação para uso da barra de progressão:

```bash
pip install tqdm
```
