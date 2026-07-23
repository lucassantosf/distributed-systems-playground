from fastapi import FastAPI, HTTPException
from grpc_clients.user import UserServiceClient
from grpc_clients.product import ProductServiceClient

app = FastAPI(title="Order Service")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "order-service"}


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
