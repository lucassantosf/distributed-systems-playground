from fastapi import FastAPI
from sqlalchemy import text

from broker import close as close_broker, publish_event
from database import SessionLocal, init_db
from repositories.product import create_product
from schemas.product import ProductCreate, ProductResponse

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


@app.post("/products", status_code=201)
def create_product_endpoint(data: ProductCreate):
    product = create_product(data.model_dump())

    publish_event({
        "event": "ProductCreated",
        "product_id": product.id,
        "name": product.name,
        "price": float(product.price),
        "category": product.category,
    })

    return ProductResponse.model_validate(product)
