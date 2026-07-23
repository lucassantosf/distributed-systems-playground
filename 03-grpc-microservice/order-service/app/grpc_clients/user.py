import grpc
from proto.generated.user import user_pb2, user_pb2_grpc
from proto.generated.common import types_pb2


class UserServiceClient:
    def __init__(self, host: str = "user-service", port: int = 50051):
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = user_pb2_grpc.UserServiceStub(self.channel)

    def get_user(self, user_id: str):
        request = user_pb2.GetUserRequest(id=user_id)
        return self.stub.GetUser(request)

    def get_user_by_email(self, email: str):
        request = user_pb2.GetUserByEmailRequest(email=email)
        return self.stub.GetUserByEmail(request)

    def list_users(self, page: int = 1, per_page: int = 100):
        request = user_pb2.ListUsersRequest(
            pagination=types_pb2.Pagination(page=page, per_page=per_page)
        )
        return self.stub.ListUsers(request)

    def create_user(self, name: str, email: str):
        request = user_pb2.CreateUserRequest(name=name, email=email)
        return self.stub.CreateUser(request)

    def close(self):
        self.channel.close()
