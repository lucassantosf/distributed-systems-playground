"""
Tipos de eventos da plataforma de Event Streaming.

Todos os eventos que trafegam pelo Kafka devem ter seu tipo
declarado aqui. Isso garante um contrato central e evita
strings avulsas espalhadas pelo código.
"""

from enum import Enum


class EventType(str, Enum):
    """
    Tipos de eventos do domínio de e-commerce / pedidos.

    Usar `str, Enum` permite serialização direta como string JSON
    sem conversão manual (ex.: json.dumps já funciona).
    """

    # ── Ciclo de vida do pedido ───────────────────────────────────────────
    ORDER_CREATED = "OrderCreated"
    ORDER_UPDATED = "OrderUpdated"

    # ── Eventos derivados do inventory-consumer ───────────────────────────
    # Publicado de volta ao Kafka após reserva de estoque (Card 25)
    INVENTORY_RESERVED = "InventoryReserved"

    @property
    def topic(self) -> str:
        """Retorna o nome oficial do tópico Kafka associado a este tipo de evento."""
        return EVENT_TOPIC_MAP[self]


# ── Mapeamento Centralizado de Tópicos por EventType (Card 8) ───────────────
EVENT_TOPIC_MAP: dict[EventType, str] = {
    EventType.ORDER_CREATED: "orders.created",
    EventType.ORDER_UPDATED: "orders.updated",
    EventType.INVENTORY_RESERVED: "inventory.reserved",
}


class OrderStatus(str, Enum):
    """
    Status possíveis de um pedido ao longo do seu ciclo de vida.
    Transportado dentro do payload dos eventos de pedido.
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
