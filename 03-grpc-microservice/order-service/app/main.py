import grpc
from fastapi import FastAPI, Depends, Request
from proto.generated.user import user_pb2
from proto.generated.product import product_pb2
from proto.generated.common import types_pb2
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database import get_db, engine
from services.order import OrderService
from schemas.order import OrderCreate, OrderList, OrderResponse
from grpc_clients.user import UserServiceClient
from grpc_clients.product import ProductServiceClient
from exceptions import MicroserviceError, InsufficientStockError

app = FastAPI(title="Order Service")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = {}
    for error in exc.errors():
        loc = error["loc"]
        if len(loc) > 1:
            field = loc[-1]
        else:
            field = loc[0]
        errors[field] = error["msg"]
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Invalid request data",
            "details": errors,
        },
    )


@app.exception_handler(MicroserviceError)
async def microservice_error_handler(request, exc: MicroserviceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.service,
            "message": exc.message,
            "type": "microservice_error",
        },
    )


@app.exception_handler(InsufficientStockError)
async def insufficient_stock_handler(request, exc: InsufficientStockError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.service,
            "message": exc.message,
            "type": "insufficient_stock",
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=500,
        content={
            "error": "database_error",
            "message": "Database operation failed",
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
        },
    )


def check_database():
    try:
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return "healthy"
    except Exception:
        return "unhealthy"


def check_user_service():
    client = UserServiceClient()
    try:
        client.stub.ListUsers(
            user_pb2.ListUsersRequest(pagination=types_pb2.Pagination(page=1, per_page=1)),
            timeout=2,
        )
        return "healthy"
    except Exception:
        return "unhealthy"
    finally:
        client.close()


def check_product_service():
    client = ProductServiceClient()
    try:
        client.stub.ListProducts(
            product_pb2.ListProductsRequest(pagination=types_pb2.Pagination(page=1, per_page=1)),
            timeout=2,
        )
        return "healthy"
    except Exception:
        return "unhealthy"
    finally:
        client.close()


@app.get("/health")
def health_check():
    checks = {
        "database": check_database(),
        "user-service": check_user_service(),
        "product-service": check_product_service(),
    }
    status = "healthy"
    if any(v == "unhealthy" for v in checks.values()):
        status = "degraded"
    return {"status": status, "service": "order-service", "checks": checks}


@app.post("/orders/", response_model=OrderResponse, status_code=201)
def create_order(data: OrderCreate, db: Session = Depends(get_db)):
    service = OrderService(db)
    return service.create_order(data)


@app.get("/orders/", response_model=OrderList)
def list_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    service = OrderService(db)
    orders, total = service.list_orders(skip=skip, limit=limit)
    return OrderList(orders=orders, total=total)


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: str, db: Session = Depends(get_db)):
    import uuid
    service = OrderService(db)
    try:
        return service.get_order(uuid.UUID(order_id))
    except ValueError as e:
        raise MicroserviceError("order-service", str(e), 404)


@app.get("/orders/user/{user_id}", response_model=OrderList)
def get_orders_by_user(user_id: str, db: Session = Depends(get_db)):
    import uuid
    service = OrderService(db)
    orders = service.get_orders_by_user(uuid.UUID(user_id))
    return OrderList(orders=orders, total=len(orders))


@app.patch("/orders/{order_id}/status")
def update_order_status(order_id: str, status: str, db: Session = Depends(get_db)):
    import uuid
    service = OrderService(db)
    try:
        order = service.update_order_status(uuid.UUID(order_id), status)
        return {"order_id": str(order.id), "status": order.status}
    except ValueError as e:
        raise MicroserviceError("order-service", str(e), 400)


@app.get("/test/user-gRPC/{email}")
def test_user_gRPC(email: str):
    client = UserServiceClient()
    try:
        user = client.get_user_by_email(email)
        return {
            "source": "gRPC (user-service:50051)",
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
            }
        }
    finally:
        client.close()


@app.get("/test/product-gRPC/{product_id}")
def test_product_gRPC(product_id: str):
    client = ProductServiceClient()
    try:
        product = client.get_product(product_id)
        return {
            "source": "gRPC (product-service:50052)",
            "product": {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": product.price,
                "stock": product.stock,
                "created_at": product.created_at,
                "updated_at": product.updated_at,
            }
        }
    finally:
        client.close()


@app.get("/test/products-gRPC")
def test_list_products_gRPC():
    client = ProductServiceClient()
    try:
        response = client.list_products()
        return {
            "source": "gRPC (product-service:50052)",
            "products": [
                {
                    "id": p.id,
                    "name": p.name,
                    "price": p.price,
                    "stock": p.stock,
                }
                for p in response.products
            ],
            "total": response.pagination.total
        }
    finally:
        client.close()
