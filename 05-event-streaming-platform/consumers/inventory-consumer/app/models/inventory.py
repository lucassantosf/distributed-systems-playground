"""
Modelo SQLAlchemy para a tabela inventory_reservations no db_inventory.
Garante controle de estoque e idempotência (UNIQUE em event_id).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # event_id com unique=True é a chave para a IDEMPOTÊNCIA no consumidor
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    product_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="RESERVED")
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<InventoryReservation id={self.id} order_id={self.order_id} product={self.product_id} qty={self.quantity_reserved}>"
