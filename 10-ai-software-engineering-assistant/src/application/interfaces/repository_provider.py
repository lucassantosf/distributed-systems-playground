"""
Contrato: RepositoryProvider

Define como qualquer provedor de repositório remoto deve se comportar.
O Use Case depende desta abstração — nunca da GitHub API diretamente.

Implementação concreta: infrastructure/github/github_repository_provider.py
"""

from abc import ABC, abstractmethod

from src.application.dtos.file_content_dto import FileContentDTO


class RepositoryProvider(ABC):
    @abstractmethod
    def list_files(self, owner: str, repo: str) -> list[FileContentDTO]:
        """
        Lista e recupera o conteúdo dos arquivos de código de um repositório remoto.

        Args:
            owner: Dono do repositório (ex: "torvalds").
            repo:  Nome do repositório (ex: "linux").

        Returns:
            Lista de FileContentDTO, cada um com o path relativo e o conteúdo bruto do arquivo.
            Retorna apenas extensões de código relevantes (.py, .ts, .js, .go, .java, .rb, .rs, .md).
        """
        ...

