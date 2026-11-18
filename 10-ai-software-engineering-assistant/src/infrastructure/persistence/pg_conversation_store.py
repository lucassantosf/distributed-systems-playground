"""
Implementação PostgreSQL de ConversationStore — F2-2

Adapta a interface ConversationStore usando SQLAlchemy + PostgreSQL.
Isolada na camada de infraestrutura: o domínio e os use cases não a conhecem diretamente.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.orm import Session

from src.application.interfaces.conversation_store import ConversationStore
from src.domain.entities.conversation import Conversation, ConversationMessage
from src.infrastructure.persistence.models import (
    ConversationMessageModel,
    ConversationModel,
)

logger = logging.getLogger(__name__)


def _model_to_message(m: ConversationMessageModel) -> ConversationMessage:
    return ConversationMessage(
        id=m.id,
        conversation_id=m.conversation_id,
        role=m.role,
        content=m.content,
        sources=list(m.sources or []),
        created_at=m.created_at,
    )


def _model_to_conversation(
    m: ConversationModel, include_messages: bool = False
) -> Conversation:
    return Conversation(
        id=m.id,
        repo_id=m.repo_id,
        title=m.title,
        messages=[_model_to_message(msg) for msg in m.messages] if include_messages else [],
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class PgConversationStore(ConversationStore):
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, conversation: Conversation) -> Conversation:
        model = ConversationModel(
            id=conversation.id,
            repo_id=conversation.repo_id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        logger.info("Conversa criada: %s (repo=%s)", model.id, model.repo_id)
        return _model_to_conversation(model)

    def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        model = (
            self._db.query(ConversationModel)
            .filter(ConversationModel.id == conversation_id)
            .first()
        )
        if not model:
            return None
        return _model_to_conversation(model, include_messages=True)

    def list_by_repo(self, repo_id: UUID) -> list[Conversation]:
        models = (
            self._db.query(ConversationModel)
            .filter(ConversationModel.repo_id == repo_id)
            .order_by(ConversationModel.updated_at.desc())
            .all()
        )
        return [_model_to_conversation(m) for m in models]

    def add_message(self, message: ConversationMessage) -> ConversationMessage:
        model = ConversationMessageModel(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
            sources=list(message.sources),
            created_at=message.created_at,
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return _model_to_message(model)

    def get_messages(
        self, conversation_id: UUID, limit: int = 20
    ) -> list[ConversationMessage]:
        """Retorna as últimas `limit` mensagens em ordem cronológica."""
        models = (
            self._db.query(ConversationMessageModel)
            .filter(ConversationMessageModel.conversation_id == conversation_id)
            .order_by(ConversationMessageModel.created_at.asc())
            .limit(limit)
            .all()
        )
        return [_model_to_message(m) for m in models]

    def touch(self, conversation_id: UUID) -> None:
        """Atualiza updated_at da conversa sem carregar o objeto completo."""
        self._db.execute(
            update(ConversationModel)
            .where(ConversationModel.id == conversation_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        self._db.commit()
