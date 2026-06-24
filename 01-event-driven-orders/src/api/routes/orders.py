from fastapi import APIRouter, Depends, status, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from src.api.dependencies.db import get_db
from src.modules.orders.schemas import OrderCreate, OrderRead
from src.modules.orders.services.crud import create_order, get_order_by_id
from src.infrastructure.messaging.publisher import publish_order_created

router = APIRouter()

@router.post("/orders", status_code=status.HTTP_201_CREATED, response_model=OrderRead)
def post_order(order_in: OrderCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Create a new order and persist it to the database, then publish an event."""
    order = create_order(db, order_in)
    # publish event in background so response is fast
    background_tasks.add_task(publish_order_created, order.id)
    return order


@router.get("/orders/{order_id}", response_model=OrderRead)
def get_order(order_id: int, db: Session = Depends(get_db)):
    """Retrieve an order by its ID."""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order
