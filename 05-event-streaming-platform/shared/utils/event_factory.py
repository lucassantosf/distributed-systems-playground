"""
Factory de eventos — criação padronizada com UUID e timestamp automáticos.

Centraliza a lógica de geração de event_id, occurred_at e correlation_id,
evitando que producer-api e consumers repitam esse código.

Uso:
    from shared.utils.event_factory import create_order_created_event

    event = create_order_created_event(
        order_id="abc-123",
        payload=OrderCreatedPayload(...),
        correlation_id="req-xyz",  # opcional — gerado automaticamente se omitido
    )

    producer.produce(
        topic="orders.created",
        key=event.to_kafka_key(),
        value=event.to_kafka_value(),
    )
"""

import uuid
from datetime import datetime, timezone

from shared.schemas.events import (
    InventoryReservedEvent,
    OrderCreatedEvent,
    OrderUpdatedEvent,
)
from shared.schemas.order import (
    InventoryReservedPayload,
    OrderCreatedPayload,
    OrderUpdatedPayload,
)


def _new_event_id() -> str:
    """Gera um UUID v4 único para identificar o evento."""
    return str(uuid.uuid4())


def _now_utc() -> datetime:
    """Retorna o timestamp atual em UTC com timezone explícito."""
    return datetime.now(tz=timezone.utc)


def _ensure_correlation_id(correlation_id: str | None) -> str:
    """
    Retorna o correlation_id fornecido ou gera um novo.
    O correlation_id permite rastrear uma requisição através de múltiplos eventos.
    """
    return correlation_id or str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# Factories públicas
# ─────────────────────────────────────────────────────────────────────────────

def create_order_created_event(
    order_id: str,
    payload: OrderCreatedPayload,
    correlation_id: str | None = None,
) -> OrderCreatedEvent:
    """
    Cria um evento OrderCreated pronto para publicação no Kafka.

    Args:
        order_id:       ID do pedido. Usado também como Message Key no Kafka.
        payload:        Dados completos do pedido criado.
        correlation_id: ID de correlação da requisição. Gerado automaticamente se omitido.

    Returns:
        OrderCreatedEvent com event_id e occurred_at gerados automaticamente.
    """
    return OrderCreatedEvent(
        event_id=_new_event_id(),
        occurred_at=_now_utc(),
        correlation_id=_ensure_correlation_id(correlation_id),
        order_id=order_id,
        payload=payload,
    )


def create_order_updated_event(
    order_id: str,
    payload: OrderUpdatedPayload,
    correlation_id: str | None = None,
) -> OrderUpdatedEvent:
    """
    Cria um evento OrderUpdated pronto para publicação no Kafka.

    Args:
        order_id:       ID do pedido atualizado.
        payload:        Status anterior, novo status e motivo da atualização.
        correlation_id: ID de correlação. Deve ser o mesmo da requisição original quando disponível.

    Returns:
        OrderUpdatedEvent com event_id e occurred_at gerados automaticamente.
    """
    return OrderUpdatedEvent(
        event_id=_new_event_id(),
        occurred_at=_now_utc(),
        correlation_id=_ensure_correlation_id(correlation_id),
        order_id=order_id,
        payload=payload,
    )


def create_inventory_reserved_event(
    order_id: str,
    payload: InventoryReservedPayload,
    correlation_id: str | None = None,
) -> InventoryReservedEvent:
    """
    Cria um evento InventoryReserved para publicação pelo inventory-consumer (Card 25).

    O correlation_id deve ser herdado do OrderCreated original para manter
    a rastreabilidade da cadeia de eventos.

    Args:
        order_id:       ID do pedido que teve estoque reservado.
        payload:        Itens reservados e ID do armazém.
        correlation_id: Herdado do evento OrderCreated disparador.

    Returns:
        InventoryReservedEvent com event_id e occurred_at gerados automaticamente.
    """
    return InventoryReservedEvent(
        event_id=_new_event_id(),
        occurred_at=_now_utc(),
        correlation_id=_ensure_correlation_id(correlation_id),
        order_id=order_id,
        payload=payload,
    )
