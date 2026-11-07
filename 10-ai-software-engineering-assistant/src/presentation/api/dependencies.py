from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from src.application.interfaces.repository_store import RepositoryStore
from src.application.interfaces.task_dispatcher import TaskDispatcher
from src.application.use_cases.ingest_repository import IngestRepository
from src.infrastructure.background.asyncio_task_dispatcher import AsyncioTaskDispatcher
from src.infrastructure.persistence.database import get_db
from src.infrastructure.persistence.pg_repository_store import PgRepositoryStore

# Tipo auxiliar para injeção da sessão do SQLAlchemy
DatabaseSession = Annotated[Session, Depends(get_db)]


# ==============================================================================
# Providers de Infraestrutura
# ==============================================================================

def get_repository_store(db: DatabaseSession) -> RepositoryStore:
    return PgRepositoryStore(db)


def get_task_dispatcher() -> TaskDispatcher:
    return AsyncioTaskDispatcher()


# ==============================================================================
# Injeção de Use Cases (Application)
# ==============================================================================

def get_ingest_repository_use_case() -> IngestRepository:
    return IngestRepository()
