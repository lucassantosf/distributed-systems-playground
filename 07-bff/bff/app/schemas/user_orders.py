from pydantic import BaseModel

from app.schemas.order_detail import OrderItemDetail


class CustomerOrderSummary(BaseModel):
    order_id: int
    status: str
    total: float
    items: list[OrderItemDetail]


class UserOrdersResponse(BaseModel):
    user_id: int
    name: str
    email: str
    orders: list[CustomerOrderSummary]
    is_degraded: bool = False
