import httpx

from app.config import settings


async def get_order(order_id: int) -> dict | None:
    """Busca um pedido por ID. Retorna None se não encontrado (404)."""
    async with httpx.AsyncClient(timeout=settings.downstream_timeout) as client:
        response = await client.get(f"{settings.order_service_url}/orders/{order_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


async def list_orders() -> list[dict]:
    """Retorna a lista de todos os pedidos."""
    async with httpx.AsyncClient(timeout=settings.downstream_timeout) as client:
        response = await client.get(f"{settings.order_service_url}/orders")
        response.raise_for_status()
        return response.json()
