"""
DTO: ChatRequestDTO

Carrega os dados de entrada para o Use Case ChatWithRepository.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class ChatRequestDTO:
    repo_id: UUID
    question: str

