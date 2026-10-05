"""
bff/app/routers/bff.py — Card 20: Endpoints do BFF integrados ao docs-service via M2M

Fluxo completo:
  1. Usuário externo envia requisição para o BFF com Bearer Token de usuário.
  2. BFF valida o token do usuário via JWKS (Card 19) e extrai roles e sub.
  3. BFF obtém/reutiliza token de serviço via Client Credentials (Card 20).
  4. BFF chama o docs-service (/internal/*) usando o token de serviço.
  5. BFF aplica regras de autorização/RBAC sobre o resultado retornado pelo docs-service.
"""

from fastapi import APIRouter, Depends, HTTPException, status

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
