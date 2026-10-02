"""
auth.py — Card 19: Validação de JWT do usuário via JWKS no BFF

Fluxo:
  1. Extrai Bearer token do header Authorization.
  2. Busca chave pública do Keycloak via endpoint JWKS (cacheada em memória).
  3. Valida assinatura RS256 + exp + iss com python-jose.
  4. Retorna claims do token do usuário (sub, preferred_username, realm_access.roles, ...).
  5. Fornece helpers de RBAC (require_roles, has_role, extract_roles).
"""

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from app.config import settings

# ── Cache de chaves públicas JWKS ─────────────────────────────────────────────
_jwks_cache: list[dict] | None = None

# ── Extrator de Bearer token ──────────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=False)


# ── Funções internas de JWKS ──────────────────────────────────────────────────

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
    """Retorna as chaves JWKS do cache ou atualiza a partir do Keycloak."""
    global _jwks_cache
    if _jwks_cache is None or force_refresh:
        _jwks_cache = await _fetch_jwks()
    return _jwks_cache


def _find_key(jwks_keys: list[dict], kid: str) -> dict | None:
    """Localiza a chave correspondente pelo kid (Key ID) do header do JWT."""
    for key in jwks_keys:
        if key.get("kid") == kid:
            return key
    return None


# ── Dependency principal: get_current_user ────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """
    FastAPI Dependency — valida o Bearer JWT do usuário e retorna seus claims.

    Retorna 401 com header WWW-Authenticate: Bearer em caso de:
      - Token ausente no header Authorization
      - Token malformado ou header ilegível
      - Chave pública não encontrada no JWKS
      - Assinatura inválida, token expirado ou issuer incorreto
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação não fornecido. "
                   "Inclua o header: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Extrai o header sem validar assinatura para obter o kid
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token malformado: não foi possível ler o header do JWT.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    kid = unverified_header.get("kid")

    # Localiza a chave pública correspondente no JWKS
    keys = await _get_jwks()
    key = _find_key(keys, kid)

    # Se não encontrada, tenta atualizar o cache (caso de rotação de chaves)
    if key is None:
        keys = await _get_jwks(force_refresh=True)
        key = _find_key(keys, kid)

    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Chave pública (kid={kid}) não encontrada no JWKS do Keycloak.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Valida assinatura RS256, expiração e issuer
    expected_issuer = f"{settings.keycloak_issuer_url}/realms/{settings.realm}"
    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=expected_issuer,
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido ou expirado: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


# ── Utilitários de RBAC ───────────────────────────────────────────────────────

def extract_roles(current_user: dict) -> list[str]:
    """Extrai as realm roles do payload do JWT do usuário."""
    return current_user.get("realm_access", {}).get("roles", [])


def has_role(current_user: dict, *roles: str) -> bool:
    """Verifica se o usuário possui ao menos uma das roles especificadas."""
    user_roles = extract_roles(current_user)
    return any(r in user_roles for r in roles)


def require_roles(*roles: str):
    """
    Factory de dependency FastAPI que exige que o usuário possua ao menos uma das roles.

    Semântica HTTP:
      - 401 Unauthorized: sem token ou token inválido (herda de get_current_user)
      - 403 Forbidden: usuário autenticado com sucesso, mas sem role suficiente
    """
    async def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        user_roles = extract_roles(current_user)
        if not any(r in user_roles for r in roles):
            username = current_user.get("preferred_username", "desconhecido")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Acesso negado para '{username}'. "
                    f"Roles necessárias: {list(roles)}. "
                    f"Suas roles: {user_roles}."
                ),
            )
        return current_user

    return dependency
