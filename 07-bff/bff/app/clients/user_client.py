import httpx

from app.config import settings
from app.exceptions import BFFException


async def get_user(user_id: int) -> dict | None:
    """Busca um usuário por ID. Retorna None em 404/HTTPError. Lança BFFException em timeout."""
    async with httpx.AsyncClient(timeout=settings.downstream_timeout) as client:
        try:
            response = await client.get(f"{settings.user_service_url}/users/{user_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise BFFException(
                status_code=504,
                error=f"Timeout calling user-service (exceeded {settings.downstream_timeout}s)",
                service="user-service",
                type="timeout",
            )
        except httpx.HTTPError:
            return None


async def list_users() -> list[dict]:
    """Retorna a lista de todos os usuários. Retorna [] em HTTPError. Lança BFFException em timeout."""
    async with httpx.AsyncClient(timeout=settings.downstream_timeout) as client:
        try:
            response = await client.get(f"{settings.user_service_url}/users")
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise BFFException(
                status_code=504,
                error=f"Timeout calling user-service (exceeded {settings.downstream_timeout}s)",
                service="user-service",
                type="timeout",
            )
        except httpx.HTTPError:
            return []
