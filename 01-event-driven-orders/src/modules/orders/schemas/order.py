from __future__ import annotations

from decimal import Decimal
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    customer_name: str = Field(..., max_length=255)
    total_amount: Decimal = Field(..., gt=0)
    status: Optional[str] = Field(default="pending", max_length=50)


class OrderRead(BaseModel):
    id: int
    customer_name: str
    total_amount: Decimal
    status: str
    created_at: datetime

    class Config:
        orm_mode = True
