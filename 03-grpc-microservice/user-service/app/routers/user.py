import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas.user import UserCreate, UserList, UserResponse, UserUpdate
from services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=201)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    service = UserService(db)
    try:
        return service.create_user(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=UserList)
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = UserService(db)
    users, total = service.list_users(skip=skip, limit=limit)
    return UserList(users=users, total=total)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    service = UserService(db)
    try:
        return service.get_user(user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: uuid.UUID, data: UserUpdate, db: Session = Depends(get_db)
):
    service = UserService(db)
    try:
        return service.update_user(user_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    service = UserService(db)
    try:
        service.delete_user(user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
