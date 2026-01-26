# database.py
import asyncio
from datetime import datetime
from typing import Optional, AsyncGenerator
from sqlmodel import Field, SQLModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from settings import settings

# Garante que o diretório existe usando pathlib
settings.DB_DIR.mkdir(exist_ok=True)

# --- Engine Async (Usando a URL do settings) ---
engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)

# Factory de Sessão Async
AsyncSessionFactory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# --- Modelos de Dados ---
class ChatHistory(SQLModel, table=True):
    __tablename__ = "chat_history"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    user_message: str
    bot_response: str

    is_synthetic: bool = Field(
        default=False,
        description="Indica se é teste sintético (True) ou usuário real (False)",
    )

    user_chars: int = 0
    bot_chars: int = 0
    user_tokens: int = 0
    bot_tokens: int = 0
    request_start_time: datetime = Field(default_factory=datetime.now)
    retrieval_end_time: Optional[datetime] = None
    response_end_time: Optional[datetime] = None
    retrieval_duration_sec: float = 0.0
    generation_duration_sec: float = 0.0
    total_duration_sec: float = 0.0


class Feedback(SQLModel, table=True):
    __tablename__ = "feedback"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    message_id: int = Field(foreign_key="chat_history.id", unique=True)
    rating: str
    comment: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ValidationRun(SQLModel, table=True):
    __tablename__ = "validation_runs"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now)
    query: str
    search_type: str
    hit_rate_eval: int = 0
    mrr_eval: float = 0.0
    precision_at_k_eval: float = 0.0


class ValidationRetrievedChunk(SQLModel, table=True):
    __tablename__ = "validation_retrieved_chunks"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="validation_runs.id")
    rank: int
    chunk_content: str
    source: Optional[str] = None
    page: Optional[int] = None
    score: float
    is_correct_eval: int = 0


# --- Funções Utilitárias ---


async def init_db():
    """Cria as tabelas no banco de dados de forma assíncrona."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    print(f"Banco de dados (Async) inicializado em: {settings.DB_PATH}")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session


if __name__ == "__main__":
    asyncio.run(init_db())
