from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from src.api.dependencies.db import get_db
from src.modules.orders.schemas import OrderCreate, OrderRead
from src.modules.orders.services.crud import create_order, get_order_by_id

router = APIRouter()

@router.post("/orders", status_code=status.HTTP_201_CREATED, response_model=OrderRead)
def post_order(order_in: OrderCreate, db: Session = Depends(get_db)):
    """Create a new order and persist it to the database."""
    order = create_order(db, order_in)
    return order


@router.get("/orders/{order_id}", response_model=OrderRead)
def get_order(order_id: int, db: Session = Depends(get_db)):
    """Retrieve an order by its ID."""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order
