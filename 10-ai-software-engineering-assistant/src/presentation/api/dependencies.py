from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from src.application.chunker import chunk_files
from src.application.interfaces.embedding_provider import EmbeddingProvider
from src.application.interfaces.repository_provider import RepositoryProvider
from src.application.interfaces.repository_store import RepositoryStore
from src.application.interfaces.task_dispatcher import TaskDispatcher
from src.application.use_cases.ingest_repository import IngestRepository
from src.infrastructure.background.asyncio_task_dispatcher import AsyncioTaskDispatcher
from src.infrastructure.embeddings.openai_embedding_provider import OpenAIEmbeddingProvider
from src.infrastructure.github.github_repository_provider import GithubRepositoryProvider
from src.infrastructure.persistence.database import get_db, SessionLocal
from src.infrastructure.persistence.pg_repository_store import PgRepositoryStore
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
    return OpenAIEmbeddingProvider()


def _make_repository_store() -> RepositoryStore:
    """
    Fábrica usada pelo background job: cria um PgRepositoryStore com
    sua própria sessão SQLAlchemy, independente do request HTTP.
    """
    return PgRepositoryStore(SessionLocal())


# ==============================================================================
# Injeção de Use Cases (Application)
# ==============================================================================

def get_ingest_repository_use_case() -> IngestRepository:
    """
    Fábrica do Use Case IngestRepository.

    Passa _make_repository_store como factory para que o Use Case crie
    sua própria sessão de banco no momento de execução (background job),
    evitando o uso de uma sessão HTTP já fechada.

    vector_store é None até o card 3.4 ser implementado.
    """
    return IngestRepository(
        repository_store_factory=_make_repository_store,
        repository_provider=get_repository_provider(),
        embedding_provider=get_embedding_provider(),
        vector_store=None,          # TODO card 3.4 — PgVectorStore
        chunker=chunk_files,
    )
