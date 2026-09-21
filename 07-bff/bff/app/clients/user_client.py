import httpx

from app.config import settings


async def get_user(user_id: int) -> dict | None:
    """Busca um usuário por ID. Retorna None se não encontrado (404)."""
    async with httpx.AsyncClient(timeout=settings.downstream_timeout) as client:
        response = await client.get(f"{settings.user_service_url}/users/{user_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


async def list_users() -> list[dict]:
    """Retorna a lista de todos os usuários."""
    async with httpx.AsyncClient(timeout=settings.downstream_timeout) as client:
        response = await client.get(f"{settings.user_service_url}/users")
        response.raise_for_status()
        return response.json()
