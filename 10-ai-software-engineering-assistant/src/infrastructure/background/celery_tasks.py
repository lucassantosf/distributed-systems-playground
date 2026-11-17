"""
Tarefas assíncronas do Celery — Fase 2 (Card F2-1)

Define as tarefas consumidas pelos Celery workers via Redis broker.
Mantém Clean Architecture: não importa nada da camada de presentation.
"""

import asyncio
import logging
from uuid import UUID

from src.application.chunker import chunk_files
from src.application.dtos.ingest_repository_dto import IngestRepositoryDTO
from src.application.use_cases.ingest_repository import IngestRepository
from src.infrastructure.background.celery_app import celery_app
from src.infrastructure.embeddings.gemini_embedding_provider import GeminiEmbeddingProvider
from src.infrastructure.embeddings.openai_embedding_provider import OpenAIEmbeddingProvider
from src.infrastructure.github.github_repository_provider import GithubRepositoryProvider
from src.infrastructure.persistence.database import SessionLocal
from src.infrastructure.persistence.pg_repository_store import PgRepositoryStore
from src.infrastructure.persistence.pg_vector_store import PgVectorStore
from src.settings import settings

logger = logging.getLogger(__name__)


def _build_ingest_use_case() -> IngestRepository:
    """Fábrica independente para execução da tarefa no worker Celery."""
    if settings.embedding_provider.lower() == "gemini":
        embedding_provider = GeminiEmbeddingProvider()
    else:
        embedding_provider = OpenAIEmbeddingProvider()

    return IngestRepository(
        repository_store_factory=lambda: PgRepositoryStore(SessionLocal()),
        repository_provider=GithubRepositoryProvider(token=settings.github_token),
        embedding_provider=embedding_provider,
        vector_store_factory=lambda: PgVectorStore(SessionLocal()),
        chunker=chunk_files,
    )


@celery_app.task(name="tasks.ingest_repository", bind=True, max_retries=3)
def ingest_repository_task(self, repo_id_str: str, github_url: str) -> None:
    """
    Executa o Use Case IngestRepository em background dentro do Celery worker.
    """
    logger.info(
        "Celery worker iniciando ingest_repository_task para repo %s (%s)",
        repo_id_str,
        github_url,
    )
    dto = IngestRepositoryDTO(
        repo_id=UUID(repo_id_str),
        github_url=github_url,
    )
    use_case = _build_ingest_use_case()
    try:
        asyncio.run(use_case.execute(dto))
        logger.info("Celery task finalizada com sucesso para repo %s", repo_id_str)
    except Exception as exc:
        logger.error(
            "Erro durante ingest_repository_task para repo %s: %s",
            repo_id_str,
            exc,
            exc_info=True,
        )
        raise exc
