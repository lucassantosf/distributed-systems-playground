from sqlalchemy import Column, Integer, String, Numeric, DateTime, func

from src.infrastructure.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(255), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
