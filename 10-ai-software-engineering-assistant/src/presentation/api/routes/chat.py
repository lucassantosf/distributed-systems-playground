from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from src.application.use_cases.chat_with_repository import ChatWithRepository
from src.domain.exceptions import RepositoryNotFound, RepositoryNotReady
from src.presentation.api.dependencies import get_chat_with_repository_use_case
from src.presentation.api.schemas.chat_schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Fazer pergunta sobre um repositório indexado",
)
def chat_with_repository(
    request: ChatRequest,
    chat_use_case: Annotated[
        ChatWithRepository, Depends(get_chat_with_repository_use_case)
    ],
):
    try:
        result = chat_use_case.execute(request.to_dto())
    except RepositoryNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RepositoryNotReady as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ChatResponse.from_dto(result)
