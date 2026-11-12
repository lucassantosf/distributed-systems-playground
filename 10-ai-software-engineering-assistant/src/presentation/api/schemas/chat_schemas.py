from uuid import UUID
from pydantic import BaseModel, Field, field_validator

from src.application.dtos.chat_request_dto import ChatRequestDTO
from src.application.dtos.chat_response_dto import ChatResponseDTO


class ChatRequest(BaseModel):
    repo_id: UUID = Field(
        ...,
        description="UUID do repositório previamente submetido e indexado via POST /repos",
    )
    question: str = Field(
        ...,
        min_length=1,
        description="Pergunta em linguagem natural sobre o código do repositório",
        examples=["Como funciona a estrutura principal deste projeto?"],
    )

    @field_validator("question")
    @classmethod
    def strip_question(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("A pergunta não pode ser vazia.")
        return clean

    def to_dto(self) -> ChatRequestDTO:
        return ChatRequestDTO(repo_id=self.repo_id, question=self.question)


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]

    @classmethod
    def from_dto(cls, dto: ChatResponseDTO) -> "ChatResponse":
        return cls(answer=dto.answer, sources=dto.sources)
