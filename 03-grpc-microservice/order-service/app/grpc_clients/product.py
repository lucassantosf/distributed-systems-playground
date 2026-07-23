import grpc
from proto.generated.product import product_pb2, product_pb2_grpc
from proto.generated.common import types_pb2


class ProductServiceClient:
    def __init__(self, host: str = "product-service", port: int = 50052):
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = product_pb2_grpc.ProductServiceStub(self.channel)

    def get_product(self, product_id: str):
        request = product_pb2.GetProductRequest(id=product_id)
        return self.stub.GetProduct(request)

    def list_products(self, page: int = 1, per_page: int = 100):
        request = product_pb2.ListProductsRequest(
            pagination=types_pb2.Pagination(page=page, per_page=per_page)
        )
        return self.stub.ListProducts(request)

    def create_product(self, name: str, description: str, price: float, stock: int):
        request = product_pb2.CreateProductRequest(
            name=name,
            description=description,
            price=str(price),
            stock=stock
        )
        return self.stub.CreateProduct(request)

    def close(self):
        self.channel.close()
