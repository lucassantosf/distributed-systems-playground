from pydantic import BaseModel


class ProductReadModel(BaseModel):
    id: int
    name: str
    price: float
    category: str
    in_stock: bool
    formatted_price: str
    price_tier: str
    name_normalized: str
