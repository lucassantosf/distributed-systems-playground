from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from shared.schemas.read_models.product import ProductReadModel

from repositories.product import get_product, list_products, redis_client

app = FastAPI(title="Query API")


@app.get("/health")
async def health():
    redis_ok = False
    try:
        redis_client.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return {"status": "ok" if redis_ok else "degraded", "redis": "healthy" if redis_ok else "unhealthy"}


@app.get("/products", response_model=list[ProductReadModel])
def list_products_endpoint(
    category: str | None = None,
    in_stock: bool | None = None,
    price_tier: Literal["low", "medium", "high"] | None = None,
    q: str | None = None,
    sort: Literal["name", "price"] | None = None,
    order: Literal["asc", "desc"] = "asc",
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return list_products(
        category=category,
        in_stock=in_stock,
        price_tier=price_tier,
        q=q,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )


@app.get("/products/{product_id}", response_model=ProductReadModel)
def get_product_endpoint(product_id: int):
    product = get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
