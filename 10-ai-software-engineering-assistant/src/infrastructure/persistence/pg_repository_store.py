from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session

from src.application.interfaces.repository_store import RepositoryStore
from src.domain.entities.repository import Repository, RepositoryStatus
from src.infrastructure.persistence.models import RepositoryModel


class PgRepositoryStore(RepositoryStore):
    def __init__(self, db: Session):
        self.db = db

    def save(self, repository: Repository) -> Repository:
        model = RepositoryModel(
            id=repository.id,
            github_url=repository.github_url,
            name=repository.name,
            status=repository.status.value,
            created_at=repository.created_at,
            indexed_at=repository.indexed_at,
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return self._to_entity(model)

    def get_by_id(self, repo_id: UUID) -> Repository | None:
        model = self.db.query(RepositoryModel).filter(RepositoryModel.id == repo_id).first()
        if not model:
            return None
        return self._to_entity(model)

    def update_status(self, repo_id: UUID, status: RepositoryStatus) -> None:
        model = self.db.query(RepositoryModel).filter(RepositoryModel.id == repo_id).first()
        if model:
            model.status = status.value
            if status == RepositoryStatus.READY:
                model.indexed_at = datetime.now(timezone.utc)
            self.db.commit()

    @staticmethod
    def _to_entity(model: RepositoryModel) -> Repository:
        return Repository(
            id=model.id,
            github_url=model.github_url,
            name=model.name,
            status=RepositoryStatus(model.status),
            created_at=model.created_at,
            indexed_at=model.indexed_at,
        )

