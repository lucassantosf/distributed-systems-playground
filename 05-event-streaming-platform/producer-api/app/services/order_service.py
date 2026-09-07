"""
Serviço de pedidos — lógica de negócio do producer-api.

Responsável por:
  1. Persistir o pedido no PostgreSQL (db_producer)
  2. Publicar o evento correspondente no Kafka via roteamento automático (Card 8)
  3. Retornar o resultado para a camada de API

Fluxo: HTTP request → order_service → PostgreSQL + Kafka → response
"""

import logging
import time
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.kafka.producer import KafkaProducerWrapper
from app.metrics import (
    kafka_events_published_total,
    kafka_publish_duration_seconds,
    orders_created_total,
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
    simulate_error: str | None = None,
    fail_until_retry: int = 1,
) -> tuple[Order, bool]:
    """
    Cria um pedido no banco e publica o evento OrderCreated no Kafka via roteamento tipado.

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
    orders_created_total.inc()

    # ── 3. Publicar evento no Kafka com roteamento automático (Card 8) ─────
    event_published = False
    topic_name = "orders.created"
    start_time = time.perf_counter()
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
            simulate_error=simulate_error,
            fail_until_retry=fail_until_retry,
        )
        event = create_order_created_event(order_id=order_id, payload=payload)
        topic_name = event.event_type.topic
        producer.produce_event(event)
        producer.flush()
        duration = time.perf_counter() - start_time
        kafka_publish_duration_seconds.labels(topic=topic_name).observe(duration)
        kafka_events_published_total.labels(topic=topic_name, status="success").inc()
        event_published = True
        logger.info(f"Evento OrderCreated publicado | order_id={order_id} topic={topic_name}")
    except Exception as exc:
        duration = time.perf_counter() - start_time
        kafka_publish_duration_seconds.labels(topic=topic_name).observe(duration)
        kafka_events_published_total.labels(topic=topic_name, status="error").inc()
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
    Atualiza o status de um pedido e publica o evento OrderUpdated no Kafka via roteamento tipado.

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
    topic_name = "orders.updated"
    start_time = time.perf_counter()
    try:
        payload = OrderUpdatedPayload(
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
        )
        event = create_order_updated_event(order_id=order_id, payload=payload)
        topic_name = event.event_type.topic
        producer.produce_event(event)
        producer.flush()
        duration = time.perf_counter() - start_time
        kafka_publish_duration_seconds.labels(topic=topic_name).observe(duration)
        kafka_events_published_total.labels(topic=topic_name, status="success").inc()
        event_published = True
        logger.info(f"Evento OrderUpdated publicado | order_id={order_id} topic={topic_name}")
    except Exception as exc:
        duration = time.perf_counter() - start_time
        kafka_publish_duration_seconds.labels(topic=topic_name).observe(duration)
        kafka_events_published_total.labels(topic=topic_name, status="error").inc()
        logger.error(f"Falha ao publicar evento no Kafka | order_id={order_id} erro={exc}")

    return order, event_published
