from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class SagaStatus(str, Enum):
    STARTED = "STARTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    FAILED = "FAILED"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    COMPENSATING_FAILED = "COMPENSATING_FAILED"


class OrderItemSchema(BaseModel):
    sku: str = Field(..., description="Identificador do produto")
    quantity: int = Field(..., gt=0, description="Quantidade do produto")
    unit_price: float = Field(..., gt=0.0, description="Preço unitário")


class CreateSagaRequest(BaseModel):
    order_id: str = Field(..., description="ID único do pedido")
    customer_id: str = Field(..., description="ID do cliente")
    items: List[OrderItemSchema] = Field(..., min_length=1, description="Lista de itens do pedido")
    total_amount: float = Field(..., gt=0.0, description="Valor total do pedido")
    shipping_address: str = Field(..., description="Endereço de entrega")
    payment_method: str = Field(default="credit_card", description="Método de pagamento")


class CreateSagaResponse(BaseModel):
    saga_id: str
    order_id: str
    status: SagaStatus
    message: str = "Saga iniciada com sucesso"


class StepResponse(BaseModel):
    name: str
    index: int
    status: StepStatus
    command_id: Optional[str] = None
    attempts: int = 1
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None


class SagaDetailResponse(BaseModel):
    saga_id: str
    order_id: str
    status: SagaStatus
    current_step: Optional[str] = None
    started_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    steps: List[StepResponse] = []


class SagaSummaryResponse(BaseModel):
    saga_id: str
    order_id: str
    status: SagaStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class SagaEventResponse(BaseModel):
    event_id: str
    event_type: str
    step: Optional[str] = None
    created_at: datetime
    payload: dict[str, Any] = {}


class SagaTimelineResponse(BaseModel):
    saga_id: str
    order_id: Optional[str] = None
    status: Optional[SagaStatus] = None
    total_events: int
    events: List[SagaEventResponse]

