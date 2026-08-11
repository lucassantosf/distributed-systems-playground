"""
Serviço de pedidos — lógica de negócio do producer-api.

Responsável por:
  1. Persistir o pedido no PostgreSQL (db_producer)
  2. Publicar o evento correspondente no Kafka
  3. Retornar o resultado para a camada de API

Fluxo: HTTP request → order_service → PostgreSQL + Kafka → response
"""

import logging
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.kafka.producer import (
    KafkaProducerWrapper,
    TOPIC_ORDERS_CREATED,
    TOPIC_ORDERS_UPDATED,
)
from app.models.order import Order, OrderItem
from shared.schemas.order import (
    OrderCreatedPayload,
    OrderItem as OrderItemSchema,
    OrderUpdatedPayload,
)
from shared.utils.event_factory import (
    create_order_created_event,
    create_order_updated_event,
)

logger = logging.getLogger(__name__)


def create_order(
    db: Session,
    customer_id: str,
    customer_email: str,
    items_data: list[dict],
    currency: str,
    producer: KafkaProducerWrapper,
) -> tuple[Order, bool]:
    """
    Cria um pedido no banco e publica o evento OrderCreated no Kafka.

    Returns:
        (order, event_published) — event_published=False se o Kafka falhar,
        sem reverter a persistência (o pedido já foi salvo).
    """
    # ── 1. Calcular total ─────────────────────────────────────────────────
    total_amount = sum(
        Decimal(str(item["unit_price"])) * item["quantity"]
        for item in items_data
    )

    # ── 2. Persistir no PostgreSQL ────────────────────────────────────────
    order_id = str(uuid.uuid4())
    order = Order(
        id=order_id,
        customer_id=customer_id,
        customer_email=customer_email,
        total_amount=total_amount,
        currency=currency,
        status="pending",
    )
    for item_data in items_data:
        order.items.append(
            OrderItem(
                id=str(uuid.uuid4()),
                order_id=order_id,
                product_id=item_data["product_id"],
                product_name=item_data["product_name"],
                quantity=item_data["quantity"],
                unit_price=Decimal(str(item_data["unit_price"])),
            )
        )

    db.add(order)
    db.commit()
    db.refresh(order)
    logger.info(f"Pedido persistido | order_id={order_id}")

    # ── 3. Publicar evento no Kafka ───────────────────────────────────────
    event_published = False
    try:
        payload = OrderCreatedPayload(
            customer_id=customer_id,
            customer_email=customer_email,
            items=[
                OrderItemSchema(
                    product_id=i.product_id,
                    product_name=i.product_name,
                    quantity=i.quantity,
                    unit_price=i.unit_price,
                )
                for i in order.items
            ],
            total_amount=total_amount,
            currency=currency,
            status="pending",
        )
        event = create_order_created_event(order_id=order_id, payload=payload)
        producer.produce(
            topic=TOPIC_ORDERS_CREATED,
            key=event.to_kafka_key(),
            value=event.to_kafka_value(),
        )
        producer.flush()
        event_published = True
        logger.info(f"Evento OrderCreated publicado | order_id={order_id} topic={TOPIC_ORDERS_CREATED}")
    except Exception as exc:
        logger.error(f"Falha ao publicar evento no Kafka | order_id={order_id} erro={exc}")

    return order, event_published


def update_order_status(
    db: Session,
    order_id: str,
    new_status: str,
    reason: str | None,
    producer: KafkaProducerWrapper,
) -> tuple[Order | None, bool]:
    """
    Atualiza o status de um pedido e publica o evento OrderUpdated no Kafka.

    Returns:
        (order, event_published) — order=None se o pedido não for encontrado.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return None, False

    previous_status = order.status
    order.status = new_status
    db.commit()
    db.refresh(order)
    logger.info(f"Status atualizado | order_id={order_id} {previous_status} → {new_status}")

    event_published = False
    try:
        payload = OrderUpdatedPayload(
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
        )
        event = create_order_updated_event(order_id=order_id, payload=payload)
        producer.produce(
            topic=TOPIC_ORDERS_UPDATED,
            key=event.to_kafka_key(),
            value=event.to_kafka_value(),
        )
        producer.flush()
        event_published = True
        logger.info(f"Evento OrderUpdated publicado | order_id={order_id} topic={TOPIC_ORDERS_UPDATED}")
    except Exception as exc:
        logger.error(f"Falha ao publicar evento no Kafka | order_id={order_id} erro={exc}")

    return order, event_published
