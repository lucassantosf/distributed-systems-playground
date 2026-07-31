from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    price: float = Field(..., gt=0)
    stock: int = Field(default=0, ge=0)
    category: str = Field(..., min_length=1, max_length=100)


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str | None
    price: float
    stock: int
    category: str

    model_config = {"from_attributes": True}
