"""
Contrato: RepositoryStore

Define como persistir e consultar metadados de repositórios.
O Use Case depende desta abstração — nunca do SQLAlchemy diretamente.

Implementação concreta: infrastructure/persistence/pg_repository_store.py

Nota de nomenclatura: o nome 'RepositoryStore' é intencional para evitar
'RepositoryRepository' (padrão Repository aplicado à entidade Repository),
que causaria confusão de leitura.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.repository import Repository, RepositoryStatus


class RepositoryStore(ABC):
    @abstractmethod
    def save(self, repository: Repository) -> Repository:
        """
        Persiste um novo repositório e retorna a entidade salva.

        Args:
            repository: Entidade de domínio Repository a ser persistida.

        Returns:
            O mesmo Repository com quaisquer campos gerados pelo banco (ex: timestamps).
        """
        ...

    @abstractmethod
    def get_by_id(self, repo_id: UUID) -> Repository | None:
        """
        Busca um repositório pelo seu ID.

        Args:
            repo_id: UUID do repositório.

        Returns:
            Entidade Repository se encontrada, None caso contrário.
        """
        ...

    @abstractmethod
    def update_status(self, repo_id: UUID, status: RepositoryStatus) -> None:
        """
        Atualiza o status de um repositório.

        Args:
            repo_id: UUID do repositório a ser atualizado.
            status:  Novo status (RepositoryStatus.INDEXING, READY, ERROR, etc.).
        """
        ...

