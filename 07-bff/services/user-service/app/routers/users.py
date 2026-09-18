from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["users"])


class User(BaseModel):
    id: int
    name: str
    email: str


USERS: list[User] = [
    User(id=1, name="Lucas Andrade",   email="lucas@example.com"),
    User(id=2, name="Ana Silva",       email="ana@example.com"),
    User(id=3, name="Carlos Mendes",   email="carlos@example.com"),
    User(id=4, name="Fernanda Costa",  email="fernanda@example.com"),
    User(id=5, name="Rafael Souza",    email="rafael@example.com"),
]

_users_by_id: dict[int, User] = {u.id: u for u in USERS}


@router.get("", response_model=list[User])
def list_users():
    return USERS


@router.get("/{user_id}", response_model=User)
def get_user(user_id: int):
    user = _users_by_id.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return user
