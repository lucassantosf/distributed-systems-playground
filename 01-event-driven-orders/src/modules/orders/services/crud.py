from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.orders.models import Order
from src.modules.orders.schemas import OrderCreate


def create_order(db: Session, order_in: OrderCreate) -> Order:
    db_obj = Order(
        customer_name=order_in.customer_name,
        total_amount=order_in.total_amount,
        status=order_in.status or "pending",
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_order_by_id(db: Session, order_id: int) -> Order | None:
    return db.query(Order).filter(Order.id == order_id).first()
