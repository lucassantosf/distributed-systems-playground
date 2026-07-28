import grpc
from proto.generated.user import user_pb2, user_pb2_grpc
from proto.generated.common import types_pb2
from exceptions import ServiceUnavailableError, ServiceTimeoutError, UserNotFoundError
from interceptors.logging import LoggingClientInterceptor

GRPC_TIMEOUT = 5


class UserServiceClient:
    def __init__(self, host: str = "user-service", port: int = 50051):
        channel = grpc.insecure_channel(f"{host}:{port}")
        interceptor = LoggingClientInterceptor("order->user", metadata_name="order-service")
        self.channel = grpc.intercept_channel(channel, interceptor)
        self.stub = user_pb2_grpc.UserServiceStub(self.channel)

    def get_user(self, user_id: str):
        request = user_pb2.GetUserRequest(id=user_id)
        try:
            return self.stub.GetUser(request, timeout=GRPC_TIMEOUT)
        except grpc.RpcError as e:
            self._handle_error(e, user_id)

    def get_user_by_email(self, email: str):
        request = user_pb2.GetUserByEmailRequest(email=email)
        try:
            return self.stub.GetUserByEmail(request, timeout=GRPC_TIMEOUT)
        except grpc.RpcError as e:
            self._handle_error(e, email)

    def list_users(self, page: int = 1, per_page: int = 100):
        request = user_pb2.ListUsersRequest(
            pagination=types_pb2.Pagination(page=page, per_page=per_page)
        )
        try:
            return self.stub.ListUsers(request, timeout=GRPC_TIMEOUT)
        except grpc.RpcError as e:
            self._handle_error(e)

    def create_user(self, name: str, email: str):
        request = user_pb2.CreateUserRequest(name=name, email=email)
        try:
            return self.stub.CreateUser(request, timeout=GRPC_TIMEOUT)
        except grpc.RpcError as e:
            self._handle_error(e)

    def close(self):
        self.channel.close()

    def _handle_error(self, e: grpc.RpcError, resource_id: str = None):
        code = e.code()
        if code == grpc.StatusCode.DEADLINE_EXCEEDED:
            raise ServiceTimeoutError("user-service")
        if code == grpc.StatusCode.UNAVAILABLE:
            raise ServiceUnavailableError("user-service")
        if code == grpc.StatusCode.NOT_FOUND:
            raise UserNotFoundError(resource_id or "unknown")
        raise ServiceUnavailableError("user-service")
