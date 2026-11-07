from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status

from src.application.interfaces.repository_store import RepositoryStore
from src.application.interfaces.task_dispatcher import TaskDispatcher
from src.application.use_cases.ingest_repository import IngestRepository
from src.domain.entities.repository import Repository, RepositoryStatus
from src.presentation.api.dependencies import (
    get_ingest_repository_use_case,
    get_repository_store,
    get_task_dispatcher,
)
from src.presentation.api.schemas.repo_schemas import (
    CreateRepositoryRequest,
    CreateRepositoryResponse,
    RepositoryResponse,
)

router = APIRouter(prefix="/repos", tags=["repositories"])


@router.post(
    "",
    response_model=CreateRepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submeter repositório para análise",
)
async def create_repository(
    request: CreateRepositoryRequest,
    repository_store: Annotated[RepositoryStore, Depends(get_repository_store)],
    task_dispatcher: Annotated[TaskDispatcher, Depends(get_task_dispatcher)],
    ingest_use_case: Annotated[IngestRepository, Depends(get_ingest_repository_use_case)],
):
    repo_name = request.extract_repo_name()

    new_repo = Repository(
        github_url=request.github_url,
        name=repo_name,
        status=RepositoryStatus.PENDING,
    )
    saved_repo = repository_store.save(new_repo)

    dto = request.to_dto(repo_id=saved_repo.id)
    task_dispatcher.dispatch(ingest_use_case.execute(dto))

    return CreateRepositoryResponse(
        id=saved_repo.id,
        status=saved_repo.status.value,
    )

@router.get(
    "/{id}",
    response_model=RepositoryResponse,
    summary="Consultar status de ingestão do repositório",
)
def get_repository(
    id: UUID,
    repository_store: Annotated[RepositoryStore, Depends(get_repository_store)],
):
    repo = repository_store.get_by_id(id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repositório com id '{id}' não encontrado.",
        )

    return RepositoryResponse(
        id=repo.id,
        github_url=repo.github_url,
        name=repo.name,
        status=repo.status.value,
        created_at=repo.created_at,
        indexed_at=repo.indexed_at,
    )

