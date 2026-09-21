import asyncio
from fastapi import APIRouter, HTTPException

from app.clients import order_client, product_client, user_client
from app.schemas.order_detail import CustomerInfo, OrderDetail, OrderItemDetail

router = APIRouter(prefix="/bff/orders", tags=["bff-orders"])


@router.get("/{order_id}", response_model=OrderDetail)
async def get_order_detail(order_id: int):
    # 1. Fetch order
    order = await order_client.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    # 2. Fetch user and product details concurrently
    user_task = user_client.get_user(order["user_id"])
    product_tasks = [
        product_client.get_product(item["product_id"]) for item in order["items"]
    ]

    results = await asyncio.gather(user_task, *product_tasks, return_exceptions=True)

    user_data = results[0]
    product_datas = results[1:]

    # Parse customer info
    if isinstance(user_data, dict) and user_data:
        customer = CustomerInfo(name=user_data["name"], email=user_data["email"])
    else:
        customer = CustomerInfo(name="Unknown", email="unknown@example.com")

    # Parse items
    items_detail = []
    for item_spec, prod_data in zip(order["items"], product_datas):
        if isinstance(prod_data, dict) and prod_data:
            prod_name = prod_data["name"]
            price = prod_data["price"]
        else:
            prod_name = f"Product #{item_spec['product_id']}"
            price = 0.0

        items_detail.append(
            OrderItemDetail(
                product_id=item_spec["product_id"],
                product_name=prod_name,
                price=price,
                quantity=item_spec["quantity"],
            )
        )

    return OrderDetail(
        order_id=order["id"],
        status=order["status"],
        total=order["total"],
        customer=customer,
        items=items_detail,
    )
