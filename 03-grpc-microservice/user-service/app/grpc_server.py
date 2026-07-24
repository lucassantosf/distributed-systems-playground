import uuid
from concurrent import futures

import grpc

from proto.generated.user import user_pb2, user_pb2_grpc
from database import SessionLocal
from services.user import UserService
from schemas.user import UserCreate


class UserServiceServicer(user_pb2_grpc.UserServiceServicer):
    def GetUser(self, request, context):
        db = SessionLocal()
        try:
            service = UserService(db)
            user = service.get_user(uuid.UUID(request.id))
            return self._user_to_proto(user)
        except ValueError as e:
            context.abort(grpc.StatusCode.NOT_FOUND, str(e))
        finally:
            db.close()

    def GetUserByEmail(self, request, context):
        db = SessionLocal()
        try:
            service = UserService(db)
            user = service.get_user_by_email(request.email)
            if not user:
                context.abort(grpc.StatusCode.NOT_FOUND, "User not found")
            return self._user_to_proto(user)
        finally:
            db.close()

    def ListUsers(self, request, context):
        db = SessionLocal()
        try:
            service = UserService(db)
            skip = (request.pagination.page - 1) * request.pagination.per_page if request.pagination.page else 0
            limit = request.pagination.per_page if request.pagination.per_page else 100
            users, total = service.list_users(skip=skip, limit=limit)

            response = user_pb2.ListUsersResponse()
            for user in users:
                response.users.append(self._user_to_proto(user))

            response.pagination.total = total
            response.pagination.page = request.pagination.page if request.pagination.page else 1
            response.pagination.per_page = request.pagination.per_page if request.pagination.per_page else 100
            response.pagination.total_pages = (total + limit - 1) // limit if limit > 0 else 0

            return response
        finally:
            db.close()

    def CreateUser(self, request, context):
        db = SessionLocal()
        try:
            service = UserService(db)
            data = UserCreate(name=request.name, email=request.email)
            user = service.create_user(data)
            return self._user_to_proto(user)
        except ValueError as e:
            context.abort(grpc.StatusCode.ALREADY_EXISTS, str(e))
        finally:
            db.close()

    def _user_to_proto(self, user):
        return user_pb2.User(
            id=str(user.id),
            name=user.name,
            email=user.email,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat(),
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    user_pb2_grpc.add_UserServiceServicer_to_server(UserServiceServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("gRPC server started on port 50051")
    server.wait_for_termination()
