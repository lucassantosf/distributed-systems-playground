"""
DTO: IngestRepositoryDTO

Carrega os dados necessários para o Use Case IngestRepository iniciar
o pipeline de ingestão de um repositório.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class IngestRepositoryDTO:
    repo_id: UUID
    github_url: str

