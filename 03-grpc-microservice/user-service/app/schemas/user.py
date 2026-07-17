import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr


class UserUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserList(BaseModel):
    users: list[UserResponse]
    total: int
