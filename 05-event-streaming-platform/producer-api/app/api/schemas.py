"""
Schemas Pydantic de request e response dos endpoints de pedidos.
Separados dos modelos de domínio (shared/) — representam o contrato HTTP da API.
"""

from decimal import Decimal
from datetime import datetime

from pydantic import BaseModel, Field


# ── Request ────────────────────────────────────────────────────────────────

class OrderItemRequest(BaseModel):
    product_id: str = Field(..., description="ID do produto")
    product_name: str = Field(..., description="Nome do produto")
    quantity: int = Field(..., gt=0, description="Quantidade")
    unit_price: Decimal = Field(..., gt=0, description="Preço unitário em BRL")


class CreateOrderRequest(BaseModel):
    customer_id: str = Field(..., description="ID do cliente")
    customer_email: str = Field(..., description="E-mail do cliente")
    items: list[OrderItemRequest] = Field(..., min_length=1, description="Itens do pedido")
    currency: str = Field(default="BRL", description="Moeda")
    simulate_error: str | None = Field(default=None, description="Simulação de erro para testes (temporary/fatal)")
    fail_until_retry: int = Field(default=1, description="Tentativa até a qual falhar")


class UpdateOrderStatusRequest(BaseModel):
    new_status: str = Field(..., description="Novo status do pedido")
    reason: str | None = Field(default=None, description="Motivo da atualização")


# ── Response ───────────────────────────────────────────────────────────────

class OrderItemResponse(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: Decimal

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    order_id: str
    customer_id: str
    customer_email: str
    items: list[OrderItemResponse]
    total_amount: Decimal
    currency: str
    status: str
    created_at: datetime
    event_published: bool
