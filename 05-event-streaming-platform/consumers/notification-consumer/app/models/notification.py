"""
Modelo SQLAlchemy para a tabela notifications no db_notification.
Garante auditoria e idempotência (UNIQUE em event_id).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # event_id com unique=True é a chave para a IDEMPOTÊNCIA no consumidor
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Notification id={self.id} order_id={self.order_id} email={self.customer_email}>"
