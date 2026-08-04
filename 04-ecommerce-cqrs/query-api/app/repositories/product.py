import json

import redis

from config import settings

redis_client = redis.from_url(settings.redis_url)

def list_products(
    category: str | None = None,
    in_stock: bool | None = None,
    price_tier: str | None = None,
    q: str | None = None,
    sort: str | None = None,
    order: str = "asc",
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    products = [json.loads(raw) for raw in redis_client.hgetall("products").values()]

    if category:
        products = [p for p in products if p["category"].lower() == category.lower()]
    if in_stock is not None:
        products = [p for p in products if p["in_stock"] == in_stock]
    if price_tier:
        products = [p for p in products if p["price_tier"] == price_tier]
    if q:
        ql = q.lower()
        products = [p for p in products if ql in p["name_normalized"]]

    if sort == "price":
        products.sort(key=lambda p: p["price"], reverse=order == "desc")
    elif sort == "name":
        products.sort(key=lambda p: p["name_normalized"], reverse=order == "desc")

    return products[offset : offset + limit]

def get_product(product_id: int) -> dict | None:
    raw = redis_client.hget("products", str(product_id))
    if raw is None:
        return None
    return json.loads(raw)
