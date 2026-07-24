import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from models.order import Order, OrderItem
from schemas.order import OrderCreate


class OrderRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, order_data: OrderCreate, total_price: float, items_data: list[dict]) -> Order:
        order = Order(
            user_id=order_data.user_id,
            total_price=total_price,
            status="pending"
        )
        self.db.add(order)
        self.db.flush()

        for item_data in items_data:
            item = OrderItem(
                order_id=order.id,
                product_id=item_data["product_id"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"]
            )
            self.db.add(item)

        self.db.commit()
        self.db.refresh(order)
        return order

    def get_by_id(self, order_id: uuid.UUID) -> Order | None:
        stmt = select(Order).options(joinedload(Order.items)).where(Order.id == order_id)
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_by_user_id(self, user_id: uuid.UUID) -> list[Order]:
        stmt = (
            select(Order)
            .options(joinedload(Order.items))
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Order]:
        stmt = (
            select(Order)
            .options(joinedload(Order.items))
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    def count(self) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(Order)
        return self.db.execute(stmt).scalar()

    def update_status(self, order: Order, status: str) -> Order:
        order.status = status
        self.db.commit()
        self.db.refresh(order)
        return order
