import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    price: Decimal = Field(..., gt=0, decimal_places=2)
    stock: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    price: Decimal | None = Field(None, gt=0, decimal_places=2)
    stock: int | None = Field(None, ge=0)


class ProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    price: Decimal
    stock: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductList(BaseModel):
    products: list[ProductResponse]
    total: int
