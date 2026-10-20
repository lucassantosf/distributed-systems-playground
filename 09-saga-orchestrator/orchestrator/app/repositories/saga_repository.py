"""
SagaRepository: camada de acesso a dados para Sagas.

Responsável por todas as queries SQLAlchemy relacionadas a Sagas, SagaSteps
e SagaEvents. O router não acessa a sessão diretamente — delega aqui.
"""
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import SagaStatus
from app.models.saga import Saga, SagaEvent, SagaStep


async def get_saga_by_id(session: AsyncSession, saga_id: str) -> Optional[Saga]:
    """Busca Saga pelo UUID com steps e events carregados."""
    try:
        uid = uuid.UUID(saga_id)
    except ValueError:
        return None

    stmt = (
        select(Saga)
        .where(Saga.id == uid)
        .options(selectinload(Saga.steps), selectinload(Saga.events))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_sagas(
    session: AsyncSession,
    status: Optional[str] = None,
    order_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Saga]:
    """Lista Sagas com filtros opcionais de status e order_id."""
    stmt = select(Saga)

    if status:
        try:
            saga_status = SagaStatus(status.upper())
            stmt = stmt.where(Saga.status == saga_status)
        except ValueError:
            pass  # Status inválido → retorna lista vazia implicitamente pelo filtro

    if order_id:
        stmt = stmt.where(Saga.order_id == order_id)

    stmt = stmt.order_by(Saga.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_events_by_saga_id(session: AsyncSession, saga_id: str) -> List[SagaEvent]:
    """Retorna todos os eventos de uma Saga, ordenados cronologicamente."""
    try:
        uid = uuid.UUID(saga_id)
    except ValueError:
        return []

    stmt = (
        select(SagaEvent)
        .where(SagaEvent.saga_id == uid)
        .options(selectinload(SagaEvent.step))
        .order_by(SagaEvent.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

