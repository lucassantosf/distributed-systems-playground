from database import SessionLocal
from models.product import Product


def create_product(data: dict) -> Product:
    db = SessionLocal()
    try:
        product = Product(**data)
        db.add(product)
        db.commit()
        db.refresh(product)
        return product
    finally:
        db.close()


def list_products() -> list[Product]:
    db = SessionLocal()
    try:
        return db.query(Product).all()
    finally:
        db.close()
