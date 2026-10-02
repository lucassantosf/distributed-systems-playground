"""
bff/app/routers/bff.py — Card 19: Endpoints do BFF protegidos por JWT e RBAC

O BFF recebe o Bearer token do usuário final, valida localmente via JWKS
e aplica as regras de controle de acesso (RBAC).

Regras de RBAC no BFF:
  - admin: visualiza todos os documentos, cria documentos e busca qualquer ID.
  - editor: visualiza apenas documentos próprios, cria novos documentos.
  - viewer: visualiza apenas documentos próprios, não pode criar (403).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import extract_roles, get_current_user, has_role, require_roles
from app.schemas.document import DocumentCreate, DocumentResponse
from app.schemas.error import ErrorResponse

router = APIRouter(prefix="/bff", tags=["BFF"])

# ── Respostas padrão para documentação OpenAPI ────────────────────────────────
_AUTH_RESPONSES = {
    401: {
        "model": ErrorResponse,
        "description": (
            "**401 Unauthorized** — Token de autenticação ausente, expirado ou inválido.\n\n"
            "Inclui o header `WWW-Authenticate: Bearer`."
        ),
    },
    403: {
        "model": ErrorResponse,
        "description": (
            "**403 Forbidden** — Usuário autenticado, porém sem permissão suficiente "
            "ou tentando acessar documento de outro usuário."
        ),
    },
}

# Base de dados em memória para demonstração no Sample C (Card 18/19)
# No Card 20, as consultas serão repassadas ao docs-service via M2M Client Credentials
SAMPLE_DOCUMENTS: list[dict] = [
    {
        "id": 1,
        "title": "Relatório de Arquitetura",
        "content": "Documento de arquitetura de sistemas distribuídos.",
        "owner_id": "5d0cca8a-69f3-45de-9620-19ae469f06e9",  # Alice (admin)
    },
    {
        "id": 2,
        "title": "Proposta de Projeto",
        "content": "Rascunho da proposta comercial para o cliente X.",
        "owner_id": "e5fdac7a-c5e2-4945-aa9f-aeba150d897a",  # Bob (editor)
    },
    {
        "id": 3,
        "title": "Guia de Boas Práticas",
        "content": "Instruções para revisão de código, padrões e testes.",
        "owner_id": "8c02af90-09e9-4d22-870a-72df2d19aecb",  # Carol (viewer)
    },
]

_next_id = 4


# ── GET /bff/documents ────────────────────────────────────────────────────────

@router.get(
    "/documents",
    response_model=list[DocumentResponse],
    responses=_AUTH_RESPONSES,
    summary="Listar documentos (filtrado por role do usuário)",
)
async def list_documents(
    current_user: dict = Depends(get_current_user),
):
    """
    Lista documentos para o usuário autenticado:
    - **admin**  → retorna todos os documentos.
    - **editor** → retorna apenas os documentos do próprio usuário (`owner_id == sub`).
    - **viewer** → retorna apenas os documentos do próprio usuário (`owner_id == sub`).

    > Rejeita requisições sem token válido com HTTP 401.
    """
    if has_role(current_user, "admin"):
        return SAMPLE_DOCUMENTS

    user_sub = current_user["sub"]
    return [doc for doc in SAMPLE_DOCUMENTS if doc["owner_id"] == user_sub]


# ── POST /bff/documents ───────────────────────────────────────────────────────

@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_AUTH_RESPONSES,
    summary="Criar documento (editor ou admin)",
)
async def create_document(
    doc: DocumentCreate,
    current_user: dict = Depends(require_roles("admin", "editor")),
):
    """
    Cria um novo documento. Requer role **editor** ou **admin**.
    O `owner_id` é atribuído automaticamente a partir do `sub` do JWT do usuário.

    > Retorna 403 Forbidden para usuários com role viewer.
    """
    global _next_id
    new_doc = {
        "id": _next_id,
        "title": doc.title,
        "content": doc.content,
        "owner_id": current_user["sub"],
    }
    _next_id += 1
    SAMPLE_DOCUMENTS.append(new_doc)
    return new_doc


# ── GET /bff/documents/{doc_id} ───────────────────────────────────────────────

@router.get(
    "/documents/{doc_id}",
    response_model=DocumentResponse,
    responses={
        **_AUTH_RESPONSES,
        404: {"model": ErrorResponse, "description": "Documento não encontrado."},
    },
    summary="Buscar documento por ID (via BFF)",
)
async def get_document(
    doc_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Busca um documento específico por ID:
    - **admin**  → pode visualizar qualquer documento.
    - **editor** / **viewer** → acessa somente o documento se for o proprietário.
    """
    doc = next((d for d in SAMPLE_DOCUMENTS if d["id"] == doc_id), None)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento {doc_id} não encontrado.",
        )

    if has_role(current_user, "admin"):
        return doc

    if doc["owner_id"] != current_user["sub"]:
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
    Retorna os claims extraídos do token JWT do usuário autenticado.
    Permite validar que o BFF identifica corretamente `sub`, `username` e `roles`.
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
