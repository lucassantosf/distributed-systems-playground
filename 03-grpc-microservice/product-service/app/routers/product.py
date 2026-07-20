import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas.product import (
    ProductCreate,
    ProductList,
    ProductResponse,
    ProductUpdate,
)
from services.product import ProductService

router = APIRouter(prefix="/products", tags=["products"])


@router.post("/", response_model=ProductResponse, status_code=201)
def create_product(data: ProductCreate, db: Session = Depends(get_db)):
    service = ProductService(db)
    try:
        return service.create_product(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=ProductList)
def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = ProductService(db)
    products, total = service.list_products(skip=skip, limit=limit)
    return ProductList(products=products, total=total)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)):
    service = ProductService(db)
    try:
        return service.get_product(product_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: uuid.UUID, data: ProductUpdate, db: Session = Depends(get_db)
):
    service = ProductService(db)
    try:
        return service.update_product(product_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: uuid.UUID, db: Session = Depends(get_db)):
    service = ProductService(db)
    try:
        service.delete_product(product_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
