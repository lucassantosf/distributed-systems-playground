"""
DTO: ChatRequestDTO

Carrega os dados de entrada para o Use Case ChatWithRepository.
F2-2: adiciona conversation_id opcional para suporte a histórico persistido.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class ChatRequestDTO:
    repo_id: UUID
    question: str
    conversation_id: UUID | None = None   # None → cria nova conversa

