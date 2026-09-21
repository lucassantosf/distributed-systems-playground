import httpx

from app.config import settings


async def get_product(product_id: int) -> dict | None:
    """Busca um produto por ID. Retorna None se não encontrado (404)."""
    async with httpx.AsyncClient(timeout=settings.downstream_timeout) as client:
        response = await client.get(f"{settings.product_service_url}/products/{product_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


async def list_products() -> list[dict]:
    """Retorna a lista de todos os produtos."""
    async with httpx.AsyncClient(timeout=settings.downstream_timeout) as client:
        response = await client.get(f"{settings.product_service_url}/products")
        response.raise_for_status()
        return response.json()
