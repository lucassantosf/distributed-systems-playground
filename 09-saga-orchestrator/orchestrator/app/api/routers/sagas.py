"""
Router de Sagas: integração completa com SagaEngine + PostgreSQL.

Card 3.3: POST /sagas dispara o fluxo real via SagaEngine (publica no RabbitMQ),
os endpoints GET consultam o PostgreSQL via SagaRepository.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.database import AsyncSessionLocal
from app.repositories.saga_repository import (
    get_events_by_saga_id,
    get_saga_by_id,
    list_sagas,
)
from app.schemas.saga import (
    CreateSagaRequest,
    CreateSagaResponse,
    SagaDetailResponse,
    SagaEventResponse,
    SagaSummaryResponse,
    SagaTimelineResponse,
    StepResponse,
)

logger = logging.getLogger("sagas-router")

router = APIRouter(prefix="/sagas", tags=["Sagas"])


def _duration_ms(start, end) -> Optional[int]:
    """Calcula duração em ms entre dois datetimes, ou None se ausente."""
    if start and end:
        return int((end - start).total_seconds() * 1000)
    return None


def _saga_to_detail(saga) -> SagaDetailResponse:
    """Converte ORM Saga → SagaDetailResponse."""
    # Identifica o step corrente: preferência para o step ativamente em execução/compensação
    current_step_name = None
    if saga.steps:
        for s in saga.steps:
            if s.status in (StepStatus.RUNNING, StepStatus.COMPENSATING):
                current_step_name = s.step_name
                break
        if not current_step_name:
            idx = min(saga.current_step_index, len(saga.steps) - 1)
            current_step_name = saga.steps[idx].step_name

    steps = [
        StepResponse(
            name=s.step_name,
            index=s.step_index,
            status=s.status,
            command_id=s.command_id,
            attempts=s.attempts,
            started_at=s.started_at,
            completed_at=s.completed_at,
            duration_ms=_duration_ms(s.started_at, s.completed_at),
            error_message=s.error_message,
        )
        for s in sorted(saga.steps, key=lambda x: x.step_index)
    ]

    return SagaDetailResponse(
        saga_id=str(saga.id),
        order_id=saga.order_id,
        status=saga.status,
        current_step=current_step_name,
        started_at=saga.created_at,
        updated_at=getattr(saga, "updated_at", None),
        completed_at=saga.completed_at,
        duration_ms=_duration_ms(saga.created_at, saga.completed_at),
        steps=steps,
    )


def _event_to_response(event) -> SagaEventResponse:
    """Converte ORM SagaEvent → SagaEventResponse."""
    step_name = None
    if getattr(event, "step", None):
        step_name = event.step.step_name
    elif getattr(event, "event_payload", None) and isinstance(event.event_payload, dict):
        step_name = event.event_payload.get("step_name")

    return SagaEventResponse(
        event_id=str(event.id),
        event_type=event.event_type,
        step=step_name,
        created_at=event.created_at,
        payload=event.event_payload or {},
    )


# ---------------------------------------------------------------------------
# POST /sagas — inicia a Saga via SagaEngine (dispara fluxo real)
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=CreateSagaResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Cria e inicia uma nova Saga",
)
async def create_saga(request: Request, body: CreateSagaRequest):
    engine = request.app.state.engine
    payload = body.model_dump()

    saga = await engine.start_saga(order_id=body.order_id, payload=payload)
    logger.info(f"Saga {saga.id} criada com status {saga.status} para order_id {body.order_id}")

    return CreateSagaResponse(
        saga_id=str(saga.id),
        order_id=saga.order_id,
        status=saga.status,
        message="Saga criada e primeiro step publicado no RabbitMQ",
    )


# ---------------------------------------------------------------------------
# GET /sagas — lista com filtros
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=List[SagaSummaryResponse],
    summary="Lista Sagas com filtros e paginação",
)
async def list_sagas_endpoint(
    status: Optional[str] = Query(None, description="Filtrar por status (ex: COMPLETED)"),
    order_id: Optional[str] = Query(None, description="Filtrar por order_id"),
    from_date: Optional[datetime] = Query(None, description="Data/hora inicial (ISO-8601)"),
    to_date: Optional[datetime] = Query(None, description="Data/hora final (ISO-8601)"),
    limit: int = Query(50, ge=1, le=100, description="Quantidade máxima de itens por página"),
    offset: int = Query(0, ge=0, description="Deslocamento para paginação"),
):
    async with AsyncSessionLocal() as session:
        sagas = await list_sagas(
            session,
            status=status,
            order_id=order_id,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )

    return [
        SagaSummaryResponse(
            saga_id=str(s.id),
            order_id=s.order_id,
            status=s.status,
            created_at=s.created_at,
            completed_at=s.completed_at,
            duration_ms=_duration_ms(s.created_at, s.completed_at),
        )
        for s in sagas
    ]


# ---------------------------------------------------------------------------
# GET /sagas/{saga_id} — detalhe completo
# ---------------------------------------------------------------------------

@router.get(
    "/{saga_id}",
    response_model=SagaDetailResponse,
    summary="Retorna detalhes completos de uma Saga",
)
async def get_saga(saga_id: str):
    async with AsyncSessionLocal() as session:
        saga = await get_saga_by_id(session, saga_id)

    if not saga:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Saga '{saga_id}' não encontrada",
        )

    return _saga_to_detail(saga)


# ---------------------------------------------------------------------------
# GET /sagas/{saga_id}/timeline — audit trail de eventos
# ---------------------------------------------------------------------------

@router.get(
    "/{saga_id}/timeline",
    response_model=SagaTimelineResponse,
    summary="Retorna o audit trail e linha do tempo de eventos da Saga",
)
async def get_saga_timeline(saga_id: str):
    async with AsyncSessionLocal() as session:
        saga = await get_saga_by_id(session, saga_id)
        if not saga:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Saga '{saga_id}' não encontrada",
            )
        events = await get_events_by_saga_id(session, saga_id)

    event_responses = [_event_to_response(e) for e in events]

    return SagaTimelineResponse(
        saga_id=str(saga.id),
        order_id=saga.order_id,
        status=saga.status,
        total_events=len(event_responses),
        events=event_responses,
    )
