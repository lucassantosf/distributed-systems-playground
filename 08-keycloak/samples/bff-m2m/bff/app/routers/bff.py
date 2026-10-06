"""
bff/app/routers/bff.py — Card 20/22: Endpoints do BFF integrados ao docs-service via M2M

Fluxo completo:
  1. Usuário externo envia requisição para o BFF com Bearer Token de usuário.
  2. BFF valida o token do usuário via JWKS (Card 19) e extrai roles e sub.
  3. BFF obtém/reutiliza token de serviço via Client Credentials (Card 20).
  4. BFF chama o docs-service (/internal/*) usando o token de serviço.
  5. BFF aplica regras de autorização/RBAC sobre o resultado retornado pelo docs-service.
  6. Endpoint de debug /bff/debug/tokens compara os tokens de usuário e de serviço (Card 22).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt

from app.auth import extract_roles, get_current_user, has_role
from app.clients.docs_client import docs_client
from app.schemas.document import DocumentResponse
from app.schemas.error import ErrorResponse

router = APIRouter(prefix="/bff", tags=["BFF"])

# ── Respostas documentadas para OpenAPI ───────────────────────────────────────
_AUTH_RESPONSES = {
    401: {
        "model": ErrorResponse,
        "description": (
            "**401 Unauthorized** — Token do usuário ausente, expirado ou inválido.\n\n"
            "Inclui o header `WWW-Authenticate: Bearer`."
        ),
    },
    403: {
        "model": ErrorResponse,
        "description": (
            "**403 Forbidden** — Usuário autenticado, porém sem permissão para acessar o recurso solicitado."
        ),
    },
    502: {
        "model": ErrorResponse,
        "description": (
            "**502 Bad Gateway** — Falha de comunicação entre o BFF e o docs-service downstream."
        ),
    },
    503: {
        "model": ErrorResponse,
        "description": (
            "**503 Service Unavailable** — Keycloak indisponível para validação JWKS ou emissão de token de serviço."
        ),
    },
}


# ── GET /bff/documents ────────────────────────────────────────────────────────

@router.get(
    "/documents",
    response_model=list[DocumentResponse],
    responses=_AUTH_RESPONSES,
    summary="Listar documentos (BFF → docs-service via M2M + filtro RBAC)",
)
async def list_documents(
    current_user: dict = Depends(get_current_user),
):
    """
    1. Valida o token JWT do usuário no BFF.
    2. Busca todos os documentos no docs-service interno via token de serviço M2M (Client Credentials).
    3. Aplica filtro baseado na role do usuário:
       - **admin**: recebe todos os documentos.
       - **editor** / **viewer**: recebe apenas documentos de sua propriedade (`owner_id == sub`).
    """
    all_documents = await docs_client.get_documents()

    if has_role(current_user, "admin"):
        return all_documents

    user_sub = current_user["sub"]
    return [doc for doc in all_documents if doc.get("owner_id") == user_sub]


# ── GET /bff/documents/{doc_id} ───────────────────────────────────────────────

@router.get(
    "/documents/{doc_id}",
    response_model=DocumentResponse,
    responses={
        **_AUTH_RESPONSES,
        404: {"model": ErrorResponse, "description": "Documento não encontrado."},
    },
    summary="Buscar documento por ID (BFF → docs-service via M2M)",
)
async def get_document(
    doc_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    1. Valida o token JWT do usuário no BFF.
    2. Busca o documento no docs-service interno usando o token de serviço M2M.
    3. Aplica regras de autorização:
       - **admin**: pode acessar qualquer documento.
       - **editor** / **viewer**: acessa apenas se for proprietário (`403` se pertencer a outro usuário).
    """
    doc = await docs_client.get_document_by_id(doc_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento {doc_id} não encontrado.",
        )

    if has_role(current_user, "admin"):
        return doc

    if doc.get("owner_id") != current_user["sub"]:
        username = current_user.get("preferred_username", "desconhecido")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Acesso negado para '{username}'. "
                "Este documento pertence a outro usuário."
            ),
        )

    return doc


# ── GET /bff/me ───────────────────────────────────────────────────────────────

@router.get(
    "/me",
    responses={401: _AUTH_RESPONSES[401]},
    summary="Inspecionar token do usuário (claims do JWT)",
)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Retorna os claims extraídos do token JWT do usuário autenticado no BFF.
    """
    return {
        "sub": current_user.get("sub"),
        "username": current_user.get("preferred_username"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "roles": extract_roles(current_user),
        "token_expires_at": current_user.get("exp"),
        "issued_by": current_user.get("iss"),
    }


# ── GET /bff/debug/tokens ─────────────────────────────────────────────────────

@router.get(
    "/debug/tokens",
    responses={
        **_AUTH_RESPONSES,
    },
    summary="[DEBUG] Comparar Token de Usuário vs Token de Serviço M2M (Card 22)",
)
async def debug_tokens(current_user: dict = Depends(get_current_user)):
    """
    Card 22: Compara os dois tokens em uso na arquitetura BFF + M2M:
    1. **Token do Usuário**: quem fez a requisição para o BFF (identidade humana + RBAC).
    2. **Token de Serviço**: o token que o BFF usa para chamar o docs-service (Client Credentials M2M).

    Destaca as diferenças fundamentais de segurança e governança entre os dois tokens.
    """
    # Obtém o token de serviço M2M atualmente em cache no BFF
    service_token_raw = await docs_client.get_service_token()
    service_claims = jwt.get_unverified_claims(service_token_raw)
    service_roles = service_claims.get("realm_access", {}).get("roles", [])

    user_sub = current_user.get("sub")
    user_azp = current_user.get("azp")
    user_roles = extract_roles(current_user)
    user_username = current_user.get("preferred_username", "desconhecido")

    service_sub = service_claims.get("sub")
    service_azp = service_claims.get("azp")

    return {
        "description": "Comparação entre Token de Usuário (Frontend → BFF) e Token de Serviço (BFF → docs-service)",
        "user_token": {
            "type": "User Access Token (Authorization Code / Password Grant)",
            "subject_sub": user_sub,
            "username": user_username,
            "email": current_user.get("email"),
            "authorized_party_azp": user_azp,
            "roles": user_roles,
            "scope": current_user.get("scope"),
            "token_type": current_user.get("typ"),
            "issued_by": current_user.get("iss"),
            "expires_at": current_user.get("exp"),
            "all_claims": current_user,
        },
        "service_token": {
            "type": "M2M / Service Token (Client Credentials Grant)",
            "subject_sub": service_sub,
            "service_account_client": service_azp,
            "authorized_party_azp": service_azp,
            "roles": service_roles,
            "scope": service_claims.get("scope"),
            "token_type": service_claims.get("typ"),
            "issued_by": service_claims.get("iss"),
            "expires_at": service_claims.get("exp"),
            "all_claims": service_claims,
        },
        "key_differences": {
            "sub": {
                "user_token": f"UUID do usuário humano ({user_username})",
                "service_token": f"UUID da Service Account do client '{service_azp}' no Keycloak",
                "explanation": "No token de usuário, 'sub' é a pessoa física. No token de serviço, 'sub' é uma conta de serviço sistêmica.",
            },
            "azp": {
                "user_token": user_azp,
                "service_token": service_azp,
                "explanation": "Identifica a aplicação que solicitou a autenticação. O docs-service valida estritamente azp == 'bff-client'.",
            },
            "roles": {
                "user_token": user_roles,
                "service_token": service_roles,
                "explanation": "O token de usuário contém as permissões de negócio da pessoa (RBAC). O token M2M não tem roles de usuário.",
            },
            "scope": {
                "user_token": current_user.get("scope"),
                "service_token": service_claims.get("scope"),
                "explanation": "O token de usuário solicita scopes voltados a perfil/identidade humana ('openid', 'email', 'profile').",
            },
            "architecture_pattern": (
                "O usuário autentica no BFF com seu token pessoal. "
                "O BFF autoriza a ação (RBAC) e consulta o serviço interno usando seu próprio token M2M. "
                "Desta forma, serviços internos ficam totalmente protegidos da internet e de tokens de usuário não autorizados."
            ),
        },
    }
