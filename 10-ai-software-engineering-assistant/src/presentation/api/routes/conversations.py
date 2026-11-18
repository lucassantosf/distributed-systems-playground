"""
Rotas de Conversa — F2-2

Endpoints:
  POST /conversations           → Criar nova conversa
  GET  /conversations/{id}      → Buscar conversa com mensagens
  GET  /repos/{repo_id}/conversations → Listar conversas de um repositório
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.interfaces.conversation_store import ConversationStore
from src.domain.entities.conversation import Conversation
from src.presentation.api.dependencies import get_conversation_store
from src.presentation.api.schemas.conversation_schemas import (
    ConversationListItemResponse,
    ConversationMessageResponse,
    ConversationResponse,
    CreateConversationRequest,
)

router = APIRouter(tags=["conversations"])

ConversationStoreDep = Annotated[ConversationStore, Depends(get_conversation_store)]


def _serialize_conversation(conv: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=str(conv.id),
        repo_id=str(conv.repo_id),
        title=conv.title,
        messages=[
            ConversationMessageResponse(
                id=str(m.id),
                role=m.role,
                content=m.content,
                sources=m.sources,
                created_at=m.created_at.isoformat(),
            )
            for m in conv.messages
        ],
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
    )


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar nova conversa para um repositório",
)
def create_conversation(
    body: CreateConversationRequest,
    store: ConversationStoreDep,
):
    from src.domain.entities.conversation import Conversation

    conversation = Conversation.create(
        repo_id=body.repo_id,
        title="Nova conversa",
    )
    saved = store.create(conversation)
    return _serialize_conversation(saved)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Buscar conversa com suas mensagens",
)
def get_conversation(
    conversation_id: UUID,
    store: ConversationStoreDep,
):
    conversation = store.get_by_id(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversa {conversation_id} não encontrada.",
        )
    return _serialize_conversation(conversation)


@router.get(
    "/repos/{repo_id}/conversations",
    response_model=list[ConversationListItemResponse],
    summary="Listar conversas de um repositório",
)
def list_conversations_by_repo(
    repo_id: UUID,
    store: ConversationStoreDep,
):
    conversations = store.list_by_repo(repo_id)
    return [
        ConversationListItemResponse(
            id=str(c.id),
            repo_id=str(c.repo_id),
            title=c.title,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )
        for c in conversations
    ]
