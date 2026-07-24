import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class OrderItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(..., gt=0)


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    unit_price: float

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    user_id: uuid.UUID
    items: list[OrderItemCreate] = Field(..., min_length=1)


class OrderResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    items: list[OrderItemResponse]
    total_price: float
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderList(BaseModel):
    orders: list[OrderResponse]
    total: int
