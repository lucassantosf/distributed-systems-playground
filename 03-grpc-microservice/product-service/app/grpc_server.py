import uuid
from concurrent import futures

import grpc

from proto.generated.product import product_pb2, product_pb2_grpc
from database import SessionLocal
from services.product import ProductService
from schemas.product import ProductCreate


class ProductServiceServicer(product_pb2_grpc.ProductServiceServicer):
    def GetProduct(self, request, context):
        db = SessionLocal()
        try:
            service = ProductService(db)
            product = service.get_product(uuid.UUID(request.id))
            return self._product_to_proto(product)
        except ValueError as e:
            context.abort(grpc.StatusCode.NOT_FOUND, str(e))
        finally:
            db.close()

    def ListProducts(self, request, context):
        db = SessionLocal()
        try:
            service = ProductService(db)
            skip = (request.pagination.page - 1) * request.pagination.per_page if request.pagination.page else 0
            limit = request.pagination.per_page if request.pagination.per_page else 100
            products, total = service.list_products(skip=skip, limit=limit)

            response = product_pb2.ListProductsResponse()
            for product in products:
                response.products.append(self._product_to_proto(product))

            response.pagination.total = total
            response.pagination.page = request.pagination.page if request.pagination.page else 1
            response.pagination.per_page = request.pagination.per_page if request.pagination.per_page else 100
            response.pagination.total_pages = (total + limit - 1) // limit if limit > 0 else 0

            return response
        finally:
            db.close()

    def CreateProduct(self, request, context):
        db = SessionLocal()
        try:
            service = ProductService(db)
            data = ProductCreate(
                name=request.name,
                description=request.description if request.description else None,
                price=float(request.price),
                stock=request.stock
            )
            product = service.create_product(data)
            return self._product_to_proto(product)
        except ValueError as e:
            context.abort(grpc.StatusCode.ALREADY_EXISTS, str(e))
        finally:
            db.close()

    def _product_to_proto(self, product):
        return product_pb2.Product(
            id=str(product.id),
            name=product.name,
            description=product.description or "",
            price=str(product.price),
            stock=product.stock,
            created_at=product.created_at.isoformat(),
            updated_at=product.updated_at.isoformat(),
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    product_pb2_grpc.add_ProductServiceServicer_to_server(ProductServiceServicer(), server)
    server.add_insecure_port("[::]:50052")
    server.start()
    print("gRPC server started on port 50052")
    server.wait_for_termination()
