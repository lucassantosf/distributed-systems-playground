import uuid

from sqlalchemy.orm import Session

from repositories.product import ProductRepository
from schemas.product import ProductCreate, ProductUpdate


class ProductService:
    def __init__(self, db: Session):
        self.repository = ProductRepository(db)

    def create_product(self, data: ProductCreate):
        return self.repository.create(data)

    def get_product(self, product_id: uuid.UUID):
        product = self.repository.get_by_id(product_id)
        if not product:
            raise ValueError("Product not found")
        return product

    def list_products(self, skip: int = 0, limit: int = 100):
        products = self.repository.get_all(skip=skip, limit=limit)
        total = self.repository.count()
        return products, total

    def update_product(self, product_id: uuid.UUID, data: ProductUpdate):
        product = self.repository.get_by_id(product_id)
        if not product:
            raise ValueError("Product not found")
        return self.repository.update(product, data)

    def delete_product(self, product_id: uuid.UUID):
        product = self.repository.get_by_id(product_id)
        if not product:
            raise ValueError("Product not found")
        self.repository.delete(product)
