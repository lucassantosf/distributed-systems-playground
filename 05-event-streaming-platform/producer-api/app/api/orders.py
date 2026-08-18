"""
Router FastAPI — endpoints de pedidos.

POST   /orders                      → cria pedido + publica OrderCreated
PATCH  /orders/{order_id}/status    → atualiza status + publica OrderUpdated
GET    /orders/{order_id}           → consulta pedido (útil para validação manual)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    CreateOrderRequest,
    OrderItemResponse,
    OrderResponse,
    UpdateOrderStatusRequest,
)
from app.database import get_db
from app.kafka.producer import get_kafka_producer, KafkaProducerWrapper
from app.models.order import Order
from app.services import order_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar pedido",
    description="Persiste o pedido no PostgreSQL e publica o evento OrderCreated no Kafka.",
)
def create_order(
    body: CreateOrderRequest,
    db: Session = Depends(get_db),
    producer: KafkaProducerWrapper = Depends(get_kafka_producer),
):
    items_data = [item.model_dump() for item in body.items]

    order, event_published = order_service.create_order(
        db=db,
        customer_id=body.customer_id,
        customer_email=body.customer_email,
        items_data=items_data,
        currency=body.currency,
        producer=producer,
        simulate_error=body.simulate_error,
        fail_until_retry=body.fail_until_retry,
    )

    return OrderResponse(
        order_id=order.id,
        customer_id=order.customer_id,
        customer_email=order.customer_email,
        items=[
            OrderItemResponse(
                product_id=i.product_id,
                product_name=i.product_name,
                quantity=i.quantity,
                unit_price=i.unit_price,
            )
            for i in order.items
        ],
        total_amount=order.total_amount,
        currency=order.currency,
        status=order.status,
        created_at=order.created_at,
        event_published=event_published,
    )


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Atualizar status do pedido",
    description="Atualiza o status do pedido e publica o evento OrderUpdated no Kafka.",
)
def update_order_status(
    order_id: str,
    body: UpdateOrderStatusRequest,
    db: Session = Depends(get_db),
    producer: KafkaProducerWrapper = Depends(get_kafka_producer),
):
    order, event_published = order_service.update_order_status(
        db=db,
        order_id=order_id,
        new_status=body.new_status,
        reason=body.reason,
        producer=producer,
    )

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {order_id} não encontrado.",
        )

    return OrderResponse(
        order_id=order.id,
        customer_id=order.customer_id,
        customer_email=order.customer_email,
        items=[
            OrderItemResponse(
                product_id=i.product_id,
                product_name=i.product_name,
                quantity=i.quantity,
                unit_price=i.unit_price,
            )
            for i in order.items
        ],
        total_amount=order.total_amount,
        currency=order.currency,
        status=order.status,
        created_at=order.created_at,
        event_published=event_published,
    )


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Consultar pedido",
    description="Retorna os dados de um pedido pelo ID.",
)
def get_order(
    order_id: str,
    db: Session = Depends(get_db),
):
    order: Order | None = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {order_id} não encontrado.",
        )

    return OrderResponse(
        order_id=order.id,
        customer_id=order.customer_id,
        customer_email=order.customer_email,
        items=[
            OrderItemResponse(
                product_id=i.product_id,
                product_name=i.product_name,
                quantity=i.quantity,
                unit_price=i.unit_price,
            )
            for i in order.items
        ],
        total_amount=order.total_amount,
        currency=order.currency,
        status=order.status,
        created_at=order.created_at,
        event_published=True,
    )
