from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/products", tags=["products"])


class Product(BaseModel):
    id: int
    name: str
    price: float
    stock: int


PRODUCTS: list[Product] = [
    Product(id=1, name="Mechanical Keyboard",  price=399.90, stock=15),
    Product(id=2, name="Mouse Pad XL",         price=49.90,  stock=50),
    Product(id=3, name="Wireless Mouse",       price=189.90, stock=30),
    Product(id=4, name="27\" Monitor",          price=1299.90, stock=8),
    Product(id=5, name="USB-C Hub",            price=129.90, stock=25),
    Product(id=6, name="Webcam 1080p",         price=249.90, stock=12),
    Product(id=7, name="Headset Gamer",        price=319.90, stock=20),
    Product(id=8, name="Desk Lamp LED",        price=89.90,  stock=40),
]

_products_by_id: dict[int, Product] = {p.id: p for p in PRODUCTS}


@router.get("", response_model=list[Product])
def list_products():
    return PRODUCTS


@router.get("/{product_id}", response_model=Product)
def get_product(product_id: int):
    product = _products_by_id.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return product
