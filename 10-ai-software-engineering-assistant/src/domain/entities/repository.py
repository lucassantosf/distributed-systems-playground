"""
Entidade de domínio: Repository

Representa um repositório GitHub analisado pelo sistema.
Esta classe é pura Python — não conhece SQLAlchemy, FastAPI ou qualquer framework.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class RepositoryStatus(str, Enum):
    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"


@dataclass
class Repository:
    github_url: str
    name: str
    id: UUID = field(default_factory=uuid4)
    status: RepositoryStatus = RepositoryStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    indexed_at: datetime | None = None

