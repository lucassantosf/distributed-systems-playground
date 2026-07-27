import grpc
from proto.generated.product import product_pb2, product_pb2_grpc
from proto.generated.common import types_pb2
from exceptions import ServiceUnavailableError, ServiceTimeoutError, ProductNotFoundError

GRPC_TIMEOUT = 5

class ProductServiceClient:
    def __init__(self, host: str = "product-service", port: int = 50052):
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = product_pb2_grpc.ProductServiceStub(self.channel)

    def get_product(self, product_id: str):
        request = product_pb2.GetProductRequest(id=product_id)
        try:
            return self.stub.GetProduct(request, timeout=GRPC_TIMEOUT)
        except grpc.RpcError as e:
            self._handle_error(e, product_id)

    def list_products(self, page: int = 1, per_page: int = 100):
        request = product_pb2.ListProductsRequest(
            pagination=types_pb2.Pagination(page=page, per_page=per_page)
        )
        try:
            return self.stub.ListProducts(request, timeout=GRPC_TIMEOUT)
        except grpc.RpcError as e:
            self._handle_error(e)

    def create_product(self, name: str, description: str, price: float, stock: int):
        request = product_pb2.CreateProductRequest(
            name=name,
            description=description,
            price=str(price),
            stock=stock
        )
        try:
            return self.stub.CreateProduct(request, timeout=GRPC_TIMEOUT)
        except grpc.RpcError as e:
            self._handle_error(e)

    def close(self):
        self.channel.close()

    def _handle_error(self, e: grpc.RpcError, resource_id: str = None):
        code = e.code()
        if code == grpc.StatusCode.DEADLINE_EXCEEDED:
            raise ServiceTimeoutError("product-service")
        if code == grpc.StatusCode.UNAVAILABLE:
            raise ServiceUnavailableError("product-service")
        if code == grpc.StatusCode.NOT_FOUND:
            raise ProductNotFoundError(resource_id or "unknown")
        raise ServiceUnavailableError("product-service")