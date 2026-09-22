import asyncio
from fastapi import APIRouter

from app.clients import order_client, product_client, user_client
from app.exceptions import BFFException
from app.schemas.order_detail import (
    CustomerInfo,
    OrderDetail,
    OrderItemDetail,
    OrderSummary,
)

router = APIRouter(prefix="/bff/orders", tags=["bff-orders"])


@router.get("", response_model=list[OrderSummary])
async def list_order_summaries(delay: float = 0.0):
    params = {"delay": delay} if delay > 0 else None
    orders_task = order_client.list_orders(params=params)
    users_task = user_client.list_users()

    results = await asyncio.gather(orders_task, users_task, return_exceptions=True)

    orders_data = results[0]
    users_data = results[1]

    # Re-raise BFFExceptions (e.g. 504 timeout or 503 service_unavailable)
    if isinstance(orders_data, BFFException):
        raise orders_data
    elif isinstance(orders_data, Exception):
        raise BFFException(
            status_code=503,
            error="Critical dependency unavailable: order-service is down",
            service="order-service",
            type="service_unavailable",
        )

    users_degraded = False
    if isinstance(users_data, Exception) or not isinstance(users_data, list):
        users_data = []
        users_degraded = True

    users_by_id = {
        u["id"]: u["name"] for u in users_data if isinstance(u, dict) and "id" in u
    }

    summaries = []
    for order in orders_data:
        cust_name = users_by_id.get(order["user_id"])
        if cust_name:
            customer_name = cust_name
            is_item_degraded = users_degraded
        else:
            customer_name = "Cliente (Indisponível)"
            is_item_degraded = True

        items_count = sum(item.get("quantity", 1) for item in order.get("items", []))
        summaries.append(
            OrderSummary(
                order_id=order["id"],
                user_id=order["user_id"],
                customer_name=customer_name,
                status=order["status"],
                total=order["total"],
                items_count=items_count,
                is_degraded=is_item_degraded,
            )
        )

    return summaries


@router.get("/{order_id}", response_model=OrderDetail)
async def get_order_detail(order_id: int, delay: float = 0.0):
    params = {"delay": delay} if delay > 0 else None
    order = await order_client.get_order(order_id, params=params)
    if not order:
        raise BFFException(
            status_code=404,
            error=f"Order {order_id} not found",
            service="order-service",
            type="not_found",
        )

    user_task = user_client.get_user(order["user_id"])
    product_tasks = [
        product_client.get_product(item["product_id"]) for item in order["items"]
    ]

    results = await asyncio.gather(user_task, *product_tasks, return_exceptions=True)

    user_data = results[0]
    product_datas = results[1:]

    # Re-raise BFFExceptions if any occurred during gather (e.g. timeouts)
    if isinstance(user_data, BFFException):
        raise user_data
    for p in product_datas:
        if isinstance(p, BFFException):
            raise p

    is_degraded = False

    if isinstance(user_data, dict) and user_data:
        customer = CustomerInfo(name=user_data["name"], email=user_data["email"])
    else:
        customer = CustomerInfo(
            name="Cliente (Indisponível)", email="indisponivel@example.com"
        )
        is_degraded = True

    items_detail = []
    for item_spec, prod_data in zip(order["items"], product_datas):
        if isinstance(prod_data, dict) and prod_data:
            prod_name = prod_data["name"]
            price = prod_data["price"]
        else:
            prod_name = f"Produto #{item_spec['product_id']} (Indisponível)"
            price = 0.0
            is_degraded = True

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
        is_degraded=is_degraded,
    )
