"""
Entidades de domínio: Conversation e ConversationMessage — F2-2

Representam o histórico de uma conversa sobre um repositório.
Regras de domínio:
  - Uma conversa pertence a exatamente um repositório.
  - Mensagens têm role 'user' ou 'assistant'.
  - O domínio não conhece banco de dados, HTTP ou frameworks externos.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class ConversationMessage:
    id: UUID
    conversation_id: UUID
    role: str                          # "user" | "assistant"
    content: str
    sources: list[str] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class Conversation:
    id: UUID
    repo_id: UUID
    title: str
    messages: list[ConversationMessage] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @staticmethod
    def create(repo_id: UUID, title: str) -> "Conversation":
        """Factory conveniente para criar nova conversa com UUID gerado."""
        now = datetime.now(timezone.utc)
        return Conversation(
            id=uuid4(),
            repo_id=repo_id,
            title=title,
            messages=[],
            created_at=now,
            updated_at=now,
        )
