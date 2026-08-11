"""
Envelope padrão dos eventos da plataforma.

Todo evento que trafega pelo Kafka segue esta estrutura:

    {
        "event_id":       "uuid gerado automaticamente",
        "event_type":     "OrderCreated",
        "occurred_at":    "2026-08-10T17:00:00Z",
        "correlation_id": "uuid da requisição original",
        "order_id":       "uuid do pedido  ← também é a Message Key no Kafka",
        "payload":        { ... }
    }

A Message Key (order_id) é definida separadamente no registro Kafka.
Como todos os eventos do mesmo pedido compartilham a mesma chave,
eles são gravados na mesma partição, preservando a ordenação.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from shared.events.types import EventType
from shared.schemas.order import (
    InventoryReservedPayload,
    OrderCreatedPayload,
    OrderUpdatedPayload,
)


class BaseEvent(BaseModel):
    """
    Envelope padrão compartilhado por todos os eventos da plataforma.
    Instancie os tipos concretos (OrderCreatedEvent, etc.) em vez desta classe.
    """

    event_id: str = Field(..., description="UUID único do evento")
    event_type: EventType = Field(..., description="Tipo do evento")
    occurred_at: datetime = Field(..., description="Timestamp UTC do momento do evento")
    correlation_id: str = Field(..., description="UUID de correlação da requisição original")
    order_id: str = Field(..., description="ID do pedido — também usado como Message Key no Kafka")
    payload: dict = Field(..., description="Payload específico do evento")

    def to_kafka_value(self) -> bytes:
        """Serializa o evento para bytes JSON — formato esperado pelo producer Kafka."""
        return self.model_dump_json().encode("utf-8")

    def to_kafka_key(self) -> bytes:
        """Retorna a Message Key para o Kafka (order_id como bytes)."""
        return self.order_id.encode("utf-8")

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
        }
    }


class OrderCreatedEvent(BaseModel):
    """
    Evento publicado quando um novo pedido é criado.
    Tópico Kafka: orders.created
    """

    event_id: str = Field(..., description="UUID único do evento")
    event_type: EventType = Field(default=EventType.ORDER_CREATED, frozen=True)
    occurred_at: datetime = Field(..., description="Timestamp UTC da criação")
    correlation_id: str = Field(..., description="UUID de correlação")
    order_id: str = Field(..., description="ID do pedido — Message Key no Kafka")
    payload: OrderCreatedPayload

    def to_kafka_value(self) -> bytes:
        return self.model_dump_json().encode("utf-8")

    def to_kafka_key(self) -> bytes:
        return self.order_id.encode("utf-8")

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
        }
    }


class OrderUpdatedEvent(BaseModel):
    """
    Evento publicado quando o status de um pedido é atualizado.
    Tópico Kafka: orders.updated
    """

    event_id: str = Field(..., description="UUID único do evento")
    event_type: EventType = Field(default=EventType.ORDER_UPDATED, frozen=True)
    occurred_at: datetime = Field(..., description="Timestamp UTC da atualização")
    correlation_id: str = Field(..., description="UUID de correlação")
    order_id: str = Field(..., description="ID do pedido — Message Key no Kafka")
    payload: OrderUpdatedPayload

    def to_kafka_value(self) -> bytes:
        return self.model_dump_json().encode("utf-8")

    def to_kafka_key(self) -> bytes:
        return self.order_id.encode("utf-8")

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
        }
    }


class InventoryReservedEvent(BaseModel):
    """
    Evento publicado pelo inventory-consumer após reservar estoque.
    Tópico Kafka: inventory.reserved
    Demonstra o padrão consumidor-que-também-é-produtor (Card 25).
    """

    event_id: str = Field(..., description="UUID único do evento")
    event_type: EventType = Field(default=EventType.INVENTORY_RESERVED, frozen=True)
    occurred_at: datetime = Field(..., description="Timestamp UTC da reserva")
    correlation_id: str = Field(..., description="UUID de correlação herdado do OrderCreated")
    order_id: str = Field(..., description="ID do pedido — Message Key no Kafka")
    payload: InventoryReservedPayload

    def to_kafka_value(self) -> bytes:
        return self.model_dump_json().encode("utf-8")

    def to_kafka_key(self) -> bytes:
        return self.order_id.encode("utf-8")

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
        }
    }
