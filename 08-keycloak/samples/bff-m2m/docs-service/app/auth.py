"""
docs-service/app/auth.py — Card 21: Validação do token de serviço M2M

O docs-service NÃO conhece o usuário final.
Ele valida APENAS que o chamador é o bff-client autorizado via Client Credentials.

Fluxo:
  1. Extrai Bearer token do header Authorization.
  2. Busca chave pública do Keycloak via JWKS (cacheada em memória).
  3. Valida assinatura RS256 + exp + iss com python-jose.
  4. Verifica que o claim `azp` é exatamente o `expected_client_id` (bff-client).
     - Token de usuário humano: azp = "api-simples", "frontend-pkce", etc. → rejeitado (403)
     - Token de serviço M2M:    azp = "bff-client" → aceito (200)

Por que `azp` e não `sub`?
  No Client Credentials o `sub` é o ID da service account do bff-client no Keycloak,
  e o `azp` identifica o client que solicitou o token.
  Usar `azp` é mais explícito e direto para validar a identidade do chamador de serviço.
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


# ── Dependency principal: get_service_caller ──────────────────────────────────

async def get_service_caller(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """
    FastAPI Dependency — valida que o Bearer token é um token de serviço M2M
    emitido pelo Keycloak e que o chamador é o bff-client autorizado.

    Retorna 401 quando:
      - Header Authorization ausente ou token malformado.
      - Chave pública não encontrada no JWKS.
      - Assinatura RS256 inválida, token expirado ou issuer incorreto.

    Retorna 403 quando:
      - Token é válido, mas o `azp` não é o `expected_client_id` (bff-client).
      - Isso bloqueia chamadas diretas de usuários humanos (frontend, curl, etc.),
        mesmo que seus tokens sejam tecnicamente válidos.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Token de serviço não fornecido. "
                "Este endpoint é interno e só pode ser chamado pelo BFF via M2M."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Lê o header do JWT para extrair o kid sem validar a assinatura ainda
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token malformado: não foi possível ler o header do JWT.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    kid = unverified_header.get("kid")

    # Busca a chave pública no cache JWKS com fallback para rotação de chaves
    keys = await _get_jwks()
    key = _find_key(keys, kid)

    if key is None:
        keys = await _get_jwks(force_refresh=True)
        key = _find_key(keys, kid)

    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Chave pública (kid={kid}) não encontrada no JWKS do Keycloak.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Valida assinatura RS256 e expiração
    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_iss": False},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido ou expirado: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Valida que o issuer pertence ao Realm configurado (aceita tanto localhost quanto DNS interno)
    allowed_issuers = {
        f"{settings.keycloak_issuer_url.rstrip('/')}/realms/{settings.realm}",
        f"{settings.keycloak_url.rstrip('/')}/realms/{settings.realm}",
    }
    token_iss = payload.get("iss", "")
    if token_iss not in allowed_issuers:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Issuer inválido no token: '{token_iss}'. Esperado um de: {allowed_issuers}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Valida que o chamador é o bff-client — via claim `azp` (Authorized Party)
    # O azp identifica qual client solicitou o token ao Keycloak.
    caller_azp = payload.get("azp", "")
    if caller_azp != settings.expected_client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Acesso negado. Este endpoint só aceita tokens do {settings.expected_client_id} "
                f"via Client Credentials. Chamador identificado: '{caller_azp}'."
            ),
        )

    return payload
