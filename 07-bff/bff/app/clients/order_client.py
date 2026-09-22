import httpx

from app.config import settings
from app.exceptions import BFFException


async def get_order(order_id: int, params: dict | None = None) -> dict | None:
    """Busca um pedido por ID. Retorna None se não encontrado (404). Lança BFFException em erro."""
    async with httpx.AsyncClient(timeout=settings.downstream_timeout) as client:
        try:
            response = await client.get(
                f"{settings.order_service_url}/orders/{order_id}", params=params
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise BFFException(
                status_code=504,
                error=f"Timeout calling order-service (exceeded {settings.downstream_timeout}s)",
                service="order-service",
                type="timeout",
            )
        except httpx.HTTPError:
            raise BFFException(
                status_code=503,
                error="Critical dependency unavailable: order-service is down",
                service="order-service",
                type="service_unavailable",
            )


async def list_orders(params: dict | None = None) -> list[dict]:
    """Retorna a lista de todos os pedidos. Lança BFFException em erro."""
    async with httpx.AsyncClient(timeout=settings.downstream_timeout) as client:
        try:
            response = await client.get(
                f"{settings.order_service_url}/orders", params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise BFFException(
                status_code=504,
                error=f"Timeout calling order-service (exceeded {settings.downstream_timeout}s)",
                service="order-service",
                type="timeout",
            )
        except httpx.HTTPError:
            raise BFFException(
                status_code=503,
                error="Critical dependency unavailable: order-service is down",
                service="order-service",
                type="service_unavailable",
            )
