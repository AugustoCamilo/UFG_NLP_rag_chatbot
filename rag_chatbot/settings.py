# settings.py
import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Caminhos (Paths) ---
    # Path(__file__).parent pega a pasta onde o settings.py está (raiz)
    BASE_DIR: Path = Path(__file__).parent

    # Caminhos relativos convertidos automaticamente para absolutos
    DOCS_DIR: Path = Field(default_factory=lambda: Path("docs"))
    VECTOR_DB_DIR: Path = Field(default_factory=lambda: Path("vector_db"))
    DB_DIR: Path = Field(default_factory=lambda: Path("database"))

    @property
    def DB_PATH(self) -> str:
        return str(self.DB_DIR / "chat_solution.db")

    @property
    def VECTOR_DB_PATH(self) -> Path:
        # Garante compatibilidade caso o código chame .VECTOR_DB_PATH
        return self.VECTOR_DB_DIR

    @property
    def DATABASE_URL(self) -> str:
        # Retorna a string de conexão para o SQLModel/SQLAlchemy
        return f"sqlite+aiosqlite:///{self.DB_PATH}"

    @property
    def SYNC_DATABASE_URL(self) -> str:
        # Retorna a string para conexão síncrona (Streamlit)
        return f"sqlite:///{self.DB_PATH}"

    # --- LLM & APIs ---
    GEMINI_API_KEY: str = Field(..., description="Chave obrigatória no .env")
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash"

    # --- Embeddings & Retrieval ---
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    RERANK_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L6-v2"

    SEARCH_K_RAW: int = 20
    SEARCH_K_FINAL: int = 3

    # Carrega automaticamente do arquivo .env
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


# Instância única para ser importada em todo o projeto
settings = Settings()
