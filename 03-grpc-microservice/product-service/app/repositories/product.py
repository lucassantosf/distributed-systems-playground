import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.product import Product
from schemas.product import ProductCreate, ProductUpdate


class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: ProductCreate) -> Product:
        product = Product(**data.model_dump())
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def get_by_id(self, product_id: uuid.UUID) -> Product | None:
        return self.db.get(Product, product_id)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Product]:
        stmt = select(Product).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count(self) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(Product)
        return self.db.execute(stmt).scalar()

    def update(self, product: Product, data: ProductUpdate) -> Product:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(product, field, value)
        self.db.commit()
        self.db.refresh(product)
        return product

    def delete(self, product: Product) -> None:
        self.db.delete(product)
        self.db.commit()
