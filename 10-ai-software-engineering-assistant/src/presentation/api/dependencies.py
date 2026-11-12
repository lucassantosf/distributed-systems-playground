from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from src.application.chunker import chunk_files
from src.application.interfaces.embedding_provider import EmbeddingProvider
from src.application.interfaces.llm_provider import LLMProvider
from src.application.interfaces.repository_provider import RepositoryProvider
from src.application.interfaces.repository_store import RepositoryStore
from src.application.interfaces.task_dispatcher import TaskDispatcher
from src.application.interfaces.vector_store import VectorStore
from src.application.use_cases.chat_with_repository import ChatWithRepository
from src.application.use_cases.ingest_repository import IngestRepository
from src.infrastructure.background.asyncio_task_dispatcher import AsyncioTaskDispatcher
from src.infrastructure.embeddings.gemini_embedding_provider import GeminiEmbeddingProvider
from src.infrastructure.embeddings.openai_embedding_provider import OpenAIEmbeddingProvider
from src.infrastructure.github.github_repository_provider import GithubRepositoryProvider
from src.infrastructure.llm.gemini_llm_provider import GeminiLLMProvider
from src.infrastructure.llm.openai_llm_provider import OpenAILLMProvider
from src.infrastructure.persistence.database import get_db, SessionLocal
from src.infrastructure.persistence.pg_repository_store import PgRepositoryStore
from src.infrastructure.persistence.pg_vector_store import PgVectorStore
from src.settings import settings

# Tipo auxiliar para injeção da sessão do SQLAlchemy
DatabaseSession = Annotated[Session, Depends(get_db)]


# ==============================================================================
# Providers de Infraestrutura
# ==============================================================================

def get_repository_store(db: DatabaseSession) -> RepositoryStore:
    return PgRepositoryStore(db)


def get_task_dispatcher() -> TaskDispatcher:
    return AsyncioTaskDispatcher()


def get_repository_provider() -> RepositoryProvider:
    return GithubRepositoryProvider(token=settings.github_token)


def get_embedding_provider() -> EmbeddingProvider:
    """
    Seleciona o provedor de embeddings com base em EMBEDDING_PROVIDER no .env.
    Valores aceitos: "gemini" (padrão) | "openai"

    Para usar o Gemini (gratuito via Google AI Studio):
        EMBEDDING_PROVIDER=gemini
        GEMINI_API_KEY=AIza...
    """
    if settings.embedding_provider.lower() == "gemini":
        return GeminiEmbeddingProvider()
    return OpenAIEmbeddingProvider()


def _make_repository_store() -> RepositoryStore:
    """
    Fábrica usada pelo background job: cria um PgRepositoryStore com
    sua própria sessão SQLAlchemy, independente do request HTTP.
    """
    return PgRepositoryStore(SessionLocal())


def _make_vector_store() -> VectorStore:
    """
    Fábrica usada pelo background job: cria um PgVectorStore com
    sua própria sessão SQLAlchemy, independente do request HTTP.
    """
    return PgVectorStore(SessionLocal())


def get_vector_store(db: DatabaseSession) -> VectorStore:
    """Provider de VectorStore para rotas HTTP (usa sessão do request)."""
    return PgVectorStore(db)


def get_llm_provider() -> LLMProvider:
    """
    Seleciona o provedor de LLM com base em LLM_PROVIDER no .env.
    Valores aceitos: "gemini" (padrão) | "openai"

    Para usar o Gemini (gratuito via Google AI Studio):
        LLM_PROVIDER=gemini
        GEMINI_API_KEY=AIza...
    """
    if settings.llm_provider.lower() == "gemini":
        return GeminiLLMProvider()
    return OpenAILLMProvider()


# ==============================================================================
# Injeção de Use Cases (Application)
# ==============================================================================

def get_ingest_repository_use_case() -> IngestRepository:
    """
    Fábrica do Use Case IngestRepository.

    Passa _make_repository_store e _make_vector_store como factories para que
    o Use Case crie suas próprias sessões de banco no momento de execução
    (background job), evitando o uso de sessões HTTP já fechadas.
    """
    return IngestRepository(
        repository_store_factory=_make_repository_store,
        repository_provider=get_repository_provider(),
        embedding_provider=get_embedding_provider(),
        vector_store_factory=_make_vector_store,
        chunker=chunk_files,
    )


def get_chat_with_repository_use_case(
    repository_store: Annotated[RepositoryStore, Depends(get_repository_store)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
    llm_provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> ChatWithRepository:
    """
    Fábrica do Use Case ChatWithRepository para rotas HTTP (síncrono por request).
    """
    return ChatWithRepository(
        repository_store=repository_store,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        llm_provider=llm_provider,
        top_k=settings.vector_search_top_k,
    )
