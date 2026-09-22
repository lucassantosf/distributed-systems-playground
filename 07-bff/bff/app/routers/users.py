import asyncio
from fastapi import APIRouter

from app.clients import order_client, product_client, user_client
from app.exceptions import BFFException
from app.schemas.order_detail import OrderItemDetail
from app.schemas.user_orders import CustomerOrderSummary, UserOrdersResponse

router = APIRouter(prefix="/bff/users", tags=["bff-users"])


@router.get("/{user_id}/orders", response_model=UserOrdersResponse)
async def get_user_orders(user_id: int):
    # 1. Fetch user and all orders concurrently
    user_task = user_client.get_user(user_id)
    orders_task = order_client.list_orders()

    results = await asyncio.gather(user_task, orders_task, return_exceptions=True)

    user_data = results[0]
    orders_data = results[1]

    if isinstance(user_data, BFFException):
        raise user_data
    if isinstance(orders_data, BFFException):
        raise orders_data
    elif isinstance(orders_data, Exception):
        raise BFFException(
            status_code=503,
            error="Critical dependency unavailable: order-service is down",
            service="order-service",
            type="service_unavailable",
        )

    if not isinstance(user_data, dict) or not user_data:
        raise BFFException(
            status_code=404,
            error=f"User {user_id} not found",
            service="user-service",
            type="not_found",
        )

    is_degraded = False

    # 2. Filter orders for this user
    user_orders = [o for o in orders_data if o.get("user_id") == user_id]

    # 3. Collect unique product IDs across user's orders
    product_ids = {
        item["product_id"]
        for order in user_orders
        for item in order.get("items", [])
    }

    # 4. Fetch details for all required products in parallel
    product_tasks = [product_client.get_product(pid) for pid in product_ids]
    product_results = (
        await asyncio.gather(*product_tasks, return_exceptions=True)
        if product_tasks
        else []
    )

    for p in product_results:
        if isinstance(p, BFFException):
            raise p

    products_by_id = {}
    for pid, res in zip(product_ids, product_results):
        if isinstance(res, dict) and res:
            products_by_id[pid] = res

    # 5. Build response
    composed_orders = []
    for order in user_orders:
        items_detail = []
        for item in order.get("items", []):
            pid = item["product_id"]
            prod_info = products_by_id.get(pid)
            if not prod_info:
                is_degraded = True
            items_detail.append(
                OrderItemDetail(
                    product_id=pid,
                    product_name=prod_info["name"]
                    if prod_info
                    else f"Produto #{pid} (Indisponível)",
                    price=prod_info["price"] if prod_info else 0.0,
                    quantity=item["quantity"],
                )
            )

        composed_orders.append(
            CustomerOrderSummary(
                order_id=order["id"],
                status=order["status"],
                total=order["total"],
                items=items_detail,
            )
        )

    return UserOrdersResponse(
        user_id=user_data["id"],
        name=user_data["name"],
        email=user_data["email"],
        orders=composed_orders,
        is_degraded=is_degraded,
    )
