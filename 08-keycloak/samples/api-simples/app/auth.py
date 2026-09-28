"""
auth.py — Card 6: Validação de JWT via JWKS (local, sem chamar o Keycloak a cada request)

Fluxo:
  1. Extrai Bearer token do header Authorization
  2. Busca chave pública do Keycloak via JWKS endpoint (cacheada em memória)
  3. Valida assinatura RS256 + exp + iss com python-jose
  4. Retorna claims do token como dict (sub, preferred_username, realm_access.roles, ...)
  5. Em caso de falha → HTTP 401 com mensagem clara
"""

from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from app.config import settings

# ── Cache de chaves públicas ──────────────────────────────────────────────────
# Evita buscar o JWKS no Keycloak a cada requisição.
# Será None até a primeira requisição autenticada.
# Em caso de rotação de chaves (kid não encontrado), o cache é invalidado e
# o JWKS é buscado novamente.
_jwks_cache: list[dict] | None = None

# ── Extrator de Bearer token ──────────────────────────────────────────────────
# Retorna 403 automaticamente se o header Authorization estiver ausente.
# Usamos auto_error=False para customizar a mensagem de erro (401 em vez de 403).
_bearer = HTTPBearer(auto_error=False)


# ── Funções internas ──────────────────────────────────────────────────────────

async def _fetch_jwks() -> list[dict]:
    """Busca as chaves públicas do Keycloak e armazena no cache global."""
    jwks_url = (
        f"{settings.keycloak_url}/realms/{settings.realm}"
        "/protocol/openid-connect/certs"
    )
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            return resp.json().get("keys", [])
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Não foi possível contatar o Keycloak para buscar chaves JWKS: {exc}",
            )


async def _get_jwks(force_refresh: bool = False) -> list[dict]:
    """Retorna as chaves JWKS do cache ou busca no Keycloak se necessário."""
    global _jwks_cache
    if _jwks_cache is None or force_refresh:
        _jwks_cache = await _fetch_jwks()
    return _jwks_cache


def _find_key(jwks_keys: list[dict], kid: str) -> dict | None:
    """Localiza a chave correta no JWKS pelo kid (Key ID) do header do JWT."""
    for key in jwks_keys:
        if key.get("kid") == kid:
            return key
    return None


# ── Dependency principal ──────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """
    FastAPI Dependency — valida o Bearer JWT e retorna os claims do token.

    Inject com:
        current_user: dict = Depends(get_current_user)

    Retorna dict com todos os claims, ex:
        {
            "sub": "uuid-do-usuario",
            "preferred_username": "alice",
            "realm_access": {"roles": ["admin"]},
            "email": "alice@example.com",
            ...
        }
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação não fornecido. "
                   "Inclua o header: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Extrai kid do header do JWT sem verificar assinatura ainda
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token malformado: não foi possível ler o header do JWT.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    kid = unverified_header.get("kid")

    # Busca chave correspondente no cache
    keys = await _get_jwks()
    key = _find_key(keys, kid)

    # Se não encontrou a chave, pode ser rotação → tenta refresh uma vez
    if key is None:
        keys = await _get_jwks(force_refresh=True)
        key = _find_key(keys, kid)

    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Chave pública (kid={kid}) não encontrada no JWKS do Keycloak.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Valida assinatura, expiração e issuer com python-jose
    expected_issuer = f"{settings.keycloak_issuer_url}/realms/{settings.realm}"
    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=expected_issuer,
            # audience não é validado aqui — será controlado via RBAC (Card 7)
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido ou expirado: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def extract_roles(current_user: dict) -> list[str]:
    """Extrai as realm roles do payload do JWT."""
    return current_user.get("realm_access", {}).get("roles", [])
