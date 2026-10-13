import logging
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.schemas.saga import (
    CreateSagaRequest,
    CreateSagaResponse,
    SagaDetailResponse,
    SagaSummaryResponse,
    SagaTimelineResponse,
    SagaEventResponse,
)
from app.repositories.saga_store import saga_store

logger = logging.getLogger("sagas-router")

router = APIRouter(prefix="/sagas", tags=["Sagas"])


async def trigger_first_step_async(saga_id: str, payload: dict):
    """
    Simula o disparo assíncrono do primeiro step da Saga.
    No Epic 3 este disparo publicará o comando no RabbitMQ via SagaEngine.
    """
    logger.info(f"Disparo assíncrono do primeiro step iniciado para Saga {saga_id}")


@router.post(
    "",
    response_model=CreateSagaResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Cria e inicia uma nova Saga",
)
async def create_saga(request: CreateSagaRequest, background_tasks: BackgroundTasks):
    # Idempotência básica a nível de criação
    existing = saga_store.list_all(order_id=request.order_id)
    if existing:
        saga = existing[0]
        return CreateSagaResponse(
            saga_id=saga["saga_id"],
            order_id=saga["order_id"],
            status=saga["status"],
            message="Saga já existente para este order_id",
        )

    saga_id = saga_store.create(order_id=request.order_id, payload=request.model_dump())
    logger.info(f"Saga {saga_id} criada com status STARTED para order_id {request.order_id}")

    # Dispara o primeiro step em background sem bloquear a resposta HTTP
    background_tasks.add_task(trigger_first_step_async, saga_id, request.model_dump())

    return CreateSagaResponse(
        saga_id=saga_id,
        order_id=request.order_id,
        status="STARTED",
        message="Saga criada e primeiro step disparado assincronamente",
    )


@router.get(
    "",
    response_model=List[SagaSummaryResponse],
    summary="Lista Sagas com filtros",
)
async def list_sagas(
    status: Optional[str] = Query(None, description="Filtrar por status"),
    order_id: Optional[str] = Query(None, description="Filtrar por order_id"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    sagas = saga_store.list_all(status=status, order_id=order_id, limit=limit, offset=offset)
    return [
        SagaSummaryResponse(
            saga_id=s["saga_id"],
            order_id=s["order_id"],
            status=s["status"],
            created_at=s["started_at"],
            completed_at=s.get("completed_at"),
            duration_ms=s.get("duration_ms"),
        )
        for s in sagas
    ]


@router.get(
    "/{saga_id}",
    response_model=SagaDetailResponse,
    summary="Retorna detalhes completos de uma Saga",
)
async def get_saga(saga_id: str):
    saga = saga_store.get_by_id(saga_id)
    if not saga:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Saga '{saga_id}' não encontrada",
        )
    return SagaDetailResponse(**saga)


@router.get(
    "/{saga_id}/timeline",
    response_model=SagaTimelineResponse,
    summary="Retorna o audit trail e linha do tempo de eventos da Saga",
)
async def get_saga_timeline(saga_id: str):
    saga = saga_store.get_by_id(saga_id)
    if not saga:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Saga '{saga_id}' não encontrada",
        )

    events = saga_store.get_events(saga_id)
    return SagaTimelineResponse(
        saga_id=saga_id,
        total_events=len(events),
        events=[SagaEventResponse(**e) for e in events],
    )

