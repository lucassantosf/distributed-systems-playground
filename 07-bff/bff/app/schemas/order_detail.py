from pydantic import BaseModel


class CustomerInfo(BaseModel):
    name: str
    email: str


class OrderItemDetail(BaseModel):
    product_id: int
    product_name: str
    price: float
    quantity: int


class OrderDetail(BaseModel):
    order_id: int
    status: str
    total: float
    customer: CustomerInfo
    items: list[OrderItemDetail]
    is_degraded: bool = False


class OrderSummary(BaseModel):
    order_id: int
    user_id: int
    customer_name: str
    status: str
    total: float
    items_count: int
    is_degraded: bool = False
