import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.user import User
from schemas.user import UserCreate, UserUpdate


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: UserCreate) -> User:
        user = User(**data.model_dump())
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        stmt = select(User).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count(self) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(User)
        return self.db.execute(stmt).scalar()

    def update(self, user: User, data: UserUpdate) -> User:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()
