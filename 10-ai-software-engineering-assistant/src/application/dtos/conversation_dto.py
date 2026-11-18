"""
DTOs de Conversa — F2-2

Carregam dados de entrada/saída dos endpoints de conversas
sem expor os modelos de banco de dados.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class ConversationMessageDTO:
    id: str
    role: str                     # "user" | "assistant"
    content: str
    sources: list[str]
    created_at: str               # ISO 8601


@dataclass
class ConversationDTO:
    id: str
    repo_id: str
    title: str
    messages: list[ConversationMessageDTO]
    created_at: str
    updated_at: str


@dataclass
class ConversationListItemDTO:
    id: str
    repo_id: str
    title: str
    created_at: str
    updated_at: str
