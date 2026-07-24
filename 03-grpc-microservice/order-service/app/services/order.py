import uuid

from sqlalchemy.orm import Session

from repositories.order import OrderRepository
from schemas.order import OrderCreate
from grpc_clients.user import UserServiceClient
from grpc_clients.product import ProductServiceClient


class OrderService:
    def __init__(self, db: Session):
        self.repository = OrderRepository(db)

    def create_order(self, data: OrderCreate):
        user_client = UserServiceClient()
        product_client = ProductServiceClient()

        try:
            user = user_client.get_user(str(data.user_id))
            if not user:
                raise ValueError("User not found")
        except Exception:
            raise ValueError("User not found or unavailable")
        finally:
            user_client.close()

        total_price = 0.0
        items_data = []

        for item in data.items:
            try:
                product = product_client.get_product(str(item.product_id))
                if not product:
                    raise ValueError(f"Product {item.product_id} not found")

                if product.stock < item.quantity:
                    raise ValueError(f"Insufficient stock for product {product.name}")

                unit_price = float(product.price)
                total_price += unit_price * item.quantity

                items_data.append({
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "unit_price": unit_price
                })
            except ValueError:
                raise
            except Exception:
                raise ValueError(f"Product {item.product_id} unavailable")
            finally:
                pass

        product_client.close()

        return self.repository.create(data, total_price, items_data)

    def get_order(self, order_id: uuid.UUID):
        order = self.repository.get_by_id(order_id)
        if not order:
            raise ValueError("Order not found")
        return order

    def get_orders_by_user(self, user_id: uuid.UUID):
        return self.repository.get_by_user_id(user_id)

    def list_orders(self, skip: int = 0, limit: int = 100):
        orders = self.repository.get_all(skip=skip, limit=limit)
        total = self.repository.count()
        return orders, total

    def update_order_status(self, order_id: uuid.UUID, status: str):
        order = self.repository.get_by_id(order_id)
        if not order:
            raise ValueError("Order not found")
        valid_statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
        return self.repository.update_status(order, status)
