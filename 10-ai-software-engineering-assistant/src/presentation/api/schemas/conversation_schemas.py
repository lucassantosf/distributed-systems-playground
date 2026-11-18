"""
Schemas Pydantic para os endpoints de Conversa — F2-2
"""

from uuid import UUID
from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    repo_id: UUID = Field(..., description="UUID do repositório indexado")


class ConversationMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: list[str]
    created_at: str


class ConversationResponse(BaseModel):
    id: str
    repo_id: str
    title: str
    messages: list[ConversationMessageResponse]
    created_at: str
    updated_at: str


class ConversationListItemResponse(BaseModel):
    id: str
    repo_id: str
    title: str
    created_at: str
    updated_at: str
