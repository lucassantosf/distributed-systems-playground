"""
Modelo SQLAlchemy para a tabela inventory_reservations no db_inventory.
Garante controle de estoque e idempotência via UNIQUE(event_id, product_id).

A idempotência é garantida pelo par (event_id, product_id): o mesmo evento
Kafka pode ter múltiplos produtos, mas nunca reservar o mesmo produto duas vezes.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"
    __table_args__ = (
        # Idempotência real: o mesmo evento Kafka nunca reserva o mesmo produto duas vezes.
        UniqueConstraint("event_id", "product_id", name="uq_inventory_reservations_event_product"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="RESERVED")
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<InventoryReservation id={self.id} order_id={self.order_id} product={self.product_id} qty={self.quantity_reserved}>"
