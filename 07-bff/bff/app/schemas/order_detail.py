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
