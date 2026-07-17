import uuid

from sqlalchemy.orm import Session

from repositories.user import UserRepository
from schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    def create_user(self, data: UserCreate):
        existing = self.repository.get_by_email(data.email)
        if existing:
            raise ValueError(f"Email '{data.email}' already registered")
        return self.repository.create(data)

    def get_user(self, user_id: uuid.UUID):
        user = self.repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        return user

    def get_user_by_email(self, email: str):
        return self.repository.get_by_email(email)

    def list_users(self, skip: int = 0, limit: int = 100):
        users = self.repository.get_all(skip=skip, limit=limit)
        total = self.repository.count()
        return users, total

    def update_user(self, user_id: uuid.UUID, data: UserUpdate):
        user = self.repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        if data.email:
            existing = self.repository.get_by_email(data.email)
            if existing and existing.id != user_id:
                raise ValueError(f"Email '{data.email}' already registered")
        return self.repository.update(user, data)

    def delete_user(self, user_id: uuid.UUID):
        user = self.repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        self.repository.delete(user)
