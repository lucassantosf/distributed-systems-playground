import httpx

from app.config import settings
from app.exceptions import BFFException


async def get_product(product_id: int) -> dict | None:
    """Busca um produto por ID. Retorna None em 404/HTTPError. Lança BFFException em timeout."""
    async with httpx.AsyncClient(timeout=settings.downstream_timeout) as client:
        try:
            response = await client.get(
                f"{settings.product_service_url}/products/{product_id}"
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise BFFException(
                status_code=504,
                error=f"Timeout calling product-service (exceeded {settings.downstream_timeout}s)",
                service="product-service",
                type="timeout",
            )
        except httpx.HTTPError:
            return None


async def list_products() -> list[dict]:
    """Retorna a lista de todos os produtos. Retorna [] em HTTPError. Lança BFFException em timeout."""
    async with httpx.AsyncClient(timeout=settings.downstream_timeout) as client:
        try:
            response = await client.get(f"{settings.product_service_url}/products")
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise BFFException(
                status_code=504,
                error=f"Timeout calling product-service (exceeded {settings.downstream_timeout}s)",
                service="product-service",
                type="timeout",
            )
        except httpx.HTTPError:
            return []
