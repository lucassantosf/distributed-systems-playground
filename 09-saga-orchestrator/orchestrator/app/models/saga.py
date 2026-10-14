import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Enum,
    ForeignKey,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class SagaStatus(str, enum.Enum):
    STARTED = "STARTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    FAILED = "FAILED"


class StepStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    COMPENSATING_FAILED = "COMPENSATING_FAILED"


class Saga(Base):
    """
    Representa a instância de execução do workflow distribuído (Saga).
    """
    __tablename__ = "sagas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(
        Enum(SagaStatus, name="saga_status_enum", native_enum=True),
        nullable=False,
        default=SagaStatus.STARTED,
        index=True,
    )
    current_step_index = Column(Integer, default=0, nullable=False)
    payload = Column(JSONB, nullable=False, default=dict)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relacionamentos
    steps = relationship("SagaStep", back_populates="saga", cascade="all, delete-orphan", order_by="SagaStep.step_index")
    events = relationship("SagaEvent", back_populates="saga", cascade="all, delete-orphan", order_by="SagaEvent.created_at")


class SagaStep(Base):
    """
    Representa cada etapa individual de uma Saga.
    O command_id funciona como idempotency key de cada tentativa.
    """
    __tablename__ = "saga_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    saga_id = Column(UUID(as_uuid=True), ForeignKey("sagas.id", ondelete="CASCADE"), nullable=False, index=True)
    step_name = Column(String(100), nullable=False)
    step_index = Column(Integer, nullable=False)

    status = Column(
        Enum(StepStatus, name="step_status_enum", native_enum=True),
        nullable=False,
        default=StepStatus.PENDING,
        index=True,
    )

    # Idempotency key para a tentativa atual
    command_id = Column(String(100), unique=True, nullable=True, index=True)
    attempts = Column(Integer, default=0, nullable=False)

    payload = Column(JSONB, nullable=True, default=dict)
    result = Column(JSONB, nullable=True, default=dict)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)

    saga = relationship("Saga", back_populates="steps")
    events = relationship("SagaEvent", back_populates="step")

    __table_args__ = (
        Index("ix_saga_steps_saga_step_index", "saga_id", "step_index", unique=True),
    )


class SagaEvent(Base):
    """
    Audit trail imutável (append-only) do ciclo de vida da Saga.
    Eventos nunca são atualizados ou apagados.
    """
    __tablename__ = "saga_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    saga_id = Column(UUID(as_uuid=True), ForeignKey("sagas.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(UUID(as_uuid=True), ForeignKey("saga_steps.id", ondelete="SET NULL"), nullable=True, index=True)

    event_type = Column(String(100), nullable=False, index=True)
    event_payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    saga = relationship("Saga", back_populates="events")
    step = relationship("SagaStep", back_populates="events")

