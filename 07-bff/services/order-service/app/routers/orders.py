import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderItem(BaseModel):
    product_id: int
    quantity: int


class Order(BaseModel):
    id: int
    user_id: int
    status: str
    total: float
    items: list[OrderItem]


ORDERS: list[Order] = [
    Order(
        id=1,
        user_id=1,
        status="confirmed",
        total=449.80,
        items=[
            OrderItem(product_id=1, quantity=1),
            OrderItem(product_id=2, quantity=1),
        ],
    ),
    Order(
        id=2,
        user_id=2,
        status="pending",
        total=1299.90,
        items=[
            OrderItem(product_id=4, quantity=1),
        ],
    ),
    Order(
        id=3,
        user_id=1,
        status="shipped",
        total=319.80,
        items=[
            OrderItem(product_id=3, quantity=1),
            OrderItem(product_id=5, quantity=1),
        ],
    ),
    Order(
        id=4,
        user_id=3,
        status="delivered",
        total=339.80,
        items=[
            OrderItem(product_id=8, quantity=1),
            OrderItem(product_id=6, quantity=1),
        ],
    ),
    Order(
        id=5,
        user_id=4,
        status="confirmed",
        total=639.80,
        items=[
            OrderItem(product_id=7, quantity=2),
        ],
    ),
]

_orders_by_id: dict[int, Order] = {o.id: o for o in ORDERS}


@router.get("", response_model=list[Order])
async def list_orders(delay: float = 0.0):
    if delay > 0:
        await asyncio.sleep(delay)
    return ORDERS


@router.get("/{order_id}", response_model=Order)
async def get_order(order_id: int, delay: float = 0.0):
    if delay > 0:
        await asyncio.sleep(delay)
    order = _orders_by_id.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return order
