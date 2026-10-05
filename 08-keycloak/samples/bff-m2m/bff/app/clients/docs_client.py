"""
docs_client.py — Card 20: Cliente HTTP do BFF com autenticação M2M (Client Credentials)

Responsabilidades:
  1. Solicita token de serviço ao Keycloak via POST /token (grant_type=client_credentials).
  2. Cacheia o token em memória e reutiliza até próximo da expiração (buffer de segurança).
  3. Realiza chamadas HTTP internas para o docs-service em /internal/* enviando o Bearer token de serviço.
  4. Trata falhas de conectividade (503 para Keycloak indisponível, 502 para docs-service indisponível).
"""

import time
import httpx
from fastapi import HTTPException, status

from app.config import settings


class DocsServiceClient:
    def __init__(self):
        self._service_token: str | None = None
        self._token_expires_at: float = 0.0

    async def get_service_token(self, force_refresh: bool = False) -> str:
        """
        Obtém o token de serviço do BFF via Client Credentials.
        Se houver token em cache e ainda válido, reutiliza sem chamar o Keycloak.
        """
        now = time.time()
        # Buffer de 10 segundos antes da expiração para evitar race condition
        if not force_refresh and self._service_token and now < (self._token_expires_at - 10):
            return self._service_token

        token_url = (
            f"{settings.keycloak_url}/realms/{settings.realm}"
            "/protocol/openid-connect/token"
        )

        payload = {
            "grant_type": "client_credentials",
            "client_id": settings.client_id,
            "client_secret": settings.client_secret,
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.post(token_url, data=payload)
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Não foi possível contatar o Keycloak para obter token de serviço: {exc}",
                )

            if resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        f"Falha ao obter token de serviço no Keycloak "
                        f"(HTTP {resp.status_code}): {resp.text}"
                    ),
                )

            data = resp.json()
            self._service_token = data.get("access_token")
            expires_in = data.get("expires_in", 300)
            self._token_expires_at = now + expires_in

            return self._service_token

    def get_token_debug_info(self) -> dict:
        """Retorna informações sobre o token de serviço em cache para debug e inspeção."""
        now = time.time()
        remaining_ttl = max(0, int(self._token_expires_at - now))
        return {
            "has_token": self._service_token is not None,
            "token_preview": f"{self._service_token[:15]}..." if self._service_token else None,
            "expires_in_seconds": remaining_ttl,
            "raw_token": self._service_token,
        }

    async def _request_docs_service(
        self,
        method: str,
        path: str,
        json_body: dict | None = None,
    ) -> httpx.Response:
        """Executa requisição ao docs-service com Bearer token e retentativa em caso de 401."""
        url = f"{settings.docs_service_url.rstrip('/')}/{path.lstrip('/')}"
        token = await self.get_service_token()
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.request(method, url, headers=headers, json=json_body)
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Falha de comunicação com o docs-service ({url}): {exc}",
                )

            # Se o docs-service rejeitar com 401, força refresh do token e tenta mais 1 vez
            if resp.status_code == status.HTTP_401_UNAUTHORIZED:
                token = await self.get_service_token(force_refresh=True)
                headers["Authorization"] = f"Bearer {token}"
                try:
                    resp = await client.request(method, url, headers=headers, json=json_body)
                except httpx.HTTPError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Falha de comunicação com o docs-service após renovação de token: {exc}",
                    )

            return resp

    async def get_documents(self) -> list[dict]:
        """Busca a lista de documentos do docs-service."""
        resp = await self._request_docs_service("GET", "/internal/documents")
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"docs-service retornou status {resp.status_code}: {resp.text}",
            )
        data = resp.json()
        return data.get("documents", [])

    async def get_document_by_id(self, doc_id: int) -> dict | None:
        """Busca um documento específico por ID no docs-service."""
        resp = await self._request_docs_service("GET", f"/internal/documents/{doc_id}")
        if resp.status_code == status.HTTP_404_NOT_FOUND:
            return None
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"docs-service retornou status {resp.status_code}: {resp.text}",
            )
        data = resp.json()
        return data.get("document")


# Instância única (singleton) do cliente docs-service
docs_client = DocsServiceClient()
