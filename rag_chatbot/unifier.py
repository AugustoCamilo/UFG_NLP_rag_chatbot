import os
from pathlib import Path
from typing import List

# --- CONFIGURAÇÃO ---

# Nome do arquivo final de saída
OUTPUT_FILENAME = "projeto_unificado.txt"

# Lista de arquivos a serem unificados (Ordem importa)
# Preenchi com os arquivos do seu projeto para facilitar
FILES_TO_PROCESS: List[str] = [
    "requirements.txt",
    "config.py",
    "database.py",
    "ui_utils.py",
    "vector_retriever.py",
    "rag_chain.py",
    "ingest.py",
    "ingest_xml.py",
    "app.py",
    "validate_vector_db.py",
    "validate_evaluation.py",
    "validate_history_db.py",
]

# Mapeamento de extensão para sintaxe Markdown (para highlight correto)
EXT_TO_LANG = {
    ".py": "python",
    ".txt": "text",
    ".md": "markdown",
    ".json": "json",
    ".xml": "xml",
    ".sql": "sql",
    ".env": "bash",
}

# --- CORE ---


def get_language_tag(filepath: Path) -> str:
    """Determina a tag de linguagem para o bloco de código Markdown."""
    return EXT_TO_LANG.get(filepath.suffix.lower(), "text")


def unify_files(file_list: List[str], output_file: str) -> None:
    """
    Lê múltiplos arquivos e os consolida em um único arquivo de texto
    com formatação amigável para LLMs e humanos.
    """
    output_path = Path(output_file)

    print(f"🚀 Iniciando unificação de {len(file_list)} arquivos...")

    try:
        with open(output_path, "w", encoding="utf-8") as out:
            for filename in file_list:
                file_path = Path(filename)

                if not file_path.exists():
                    print(f"⚠️  Aviso: Arquivo não encontrado e ignorado: {filename}")
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")
                    lang_tag = get_language_tag(file_path)

                    # Formatação idêntica ao seu exemplo
                    header = f"**início arquivo {filename}**\n"
                    code_block_start = f"```{lang_tag}\n"
                    code_block_end = "\n```\n"
                    footer = f"**fim arquivo {filename}**\n"
                    separator = "\n-----\n\n"

                    # Escreve o bloco completo
                    out.write(header)
                    out.write(code_block_start)
                    out.write(content)
                    if not content.endswith("\n"):
                        out.write(
                            "\n"
                        )  # Garante quebra de linha antes de fechar o bloco
                    out.write(code_block_end)
                    out.write(footer)
                    out.write(separator)

                    print(f"✅ Processado: {filename}")

                except Exception as e:
                    print(f"❌ Erro ao ler {filename}: {e}")

        print(f"\n✨ Sucesso! Arquivo gerado em: {output_path.absolute()}")

    except IOError as e:
        print(f"❌ Erro crítico ao escrever arquivo de saída: {e}")


if __name__ == "__main__":
    unify_files(FILES_TO_PROCESS, OUTPUT_FILENAME)
