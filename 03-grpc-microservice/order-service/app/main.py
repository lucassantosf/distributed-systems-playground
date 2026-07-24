from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from services.order import OrderService
from schemas.order import OrderCreate, OrderList, OrderResponse
from grpc_clients.user import UserServiceClient
from grpc_clients.product import ProductServiceClient

app = FastAPI(title="Order Service")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "order-service"}


@app.post("/orders/", response_model=OrderResponse, status_code=201)
def create_order(data: OrderCreate, db: Session = Depends(get_db)):
    service = OrderService(db)
    try:
        return service.create_order(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
        raise HTTPException(status_code=404, detail=str(e))


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
        raise HTTPException(status_code=400, detail=str(e))


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
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"gRPC error: {str(e)}")
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
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"gRPC error: {str(e)}")
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
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"gRPC error: {str(e)}")
    finally:
        client.close()
