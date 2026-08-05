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


def update_product(product_id: int, data: dict) -> Product | None:
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product is None:
            return None
        for field, value in data.items():
            setattr(product, field, value)
        db.commit()
        db.refresh(product)
        return product
    finally:
        db.close()


def delete_product(product_id: int) -> bool:
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product is None:
            return False
        db.delete(product)
        db.commit()
        return True
    finally:
        db.close()
