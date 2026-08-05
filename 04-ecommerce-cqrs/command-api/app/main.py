from fastapi import FastAPI, HTTPException
from shared.events.product import PRODUCT_CREATED, PRODUCT_DELETED, PRODUCT_UPDATED
from sqlalchemy import text

from broker import close as close_broker, publish_event
from database import SessionLocal, init_db
from repositories.product import create_product, delete_product, list_products, update_product
from schemas.product import ProductCreate, ProductResponse, ProductUpdate

app = FastAPI(title="Command API")


@app.on_event("startup")
def on_startup():
    init_db()


@app.on_event("shutdown")
def on_shutdown():
    close_broker()


@app.get("/health")
async def health():
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        db_ok = False

    return {"status": "ok" if db_ok else "degraded", "database": "healthy" if db_ok else "unhealthy"}


@app.get("/products", response_model=list[ProductResponse])
def list_products_endpoint():
    return list_products()


@app.post("/products", status_code=201)
def create_product_endpoint(data: ProductCreate):
    product = create_product(data.model_dump())

    publish_event({
        "event": PRODUCT_CREATED,
        "product_id": product.id,
        "name": product.name,
        "price": float(product.price),
        "stock": product.stock,
        "category": product.category,
    })

    return ProductResponse.model_validate(product)


@app.put("/products/{product_id}", response_model=ProductResponse)
def update_product_endpoint(product_id: int, data: ProductUpdate):
    product = update_product(product_id, data.model_dump(exclude_unset=True))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    publish_event({
        "event": PRODUCT_UPDATED,
        "product_id": product.id,
        "name": product.name,
        "price": float(product.price),
        "stock": product.stock,
        "category": product.category,
    })

    return ProductResponse.model_validate(product)


@app.delete("/products/{product_id}", status_code=204)
def delete_product_endpoint(product_id: int):
    deleted = delete_product(product_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Product not found")

    publish_event({
        "event": PRODUCT_DELETED,
        "product_id": product_id,
    })
