from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import (
    extract_scopes,
    get_current_user,
    get_current_user_introspect,
    has_role,
    require_roles,
    require_scopes,
)
from app.schemas.document import DocumentCreate, DocumentResponse
from app.schemas.error import ErrorResponse

router = APIRouter()

# ── Respostas de erro reutilizáveis ────────────────────────────────────────────
# Declaradas aqui para não repetir em cada endpoint.
# Aparecem no Swagger UI (http://localhost:8001/docs) como respostas documentadas.

_AUTH_RESPONSES = {
    401: {
        "model": ErrorResponse,
        "description": (
            "**401 Unauthorized** — Não sei quem você é.\n\n"
            "Causas: token ausente, malformado, expirado ou com assinatura inválida.\n"
            "O header `WWW-Authenticate: Bearer` é incluído na resposta."
        ),
    },
    403: {
        "model": ErrorResponse,
        "description": (
            "**403 Forbidden** — Sei quem você é, mas não pode fazer isso.\n\n"
            "Token válido, porém o usuário não tem a role necessária, "
            "o token não possui o scope necessário, ou o usuário não é dono do recurso."
        ),
    },
}

# Dados em memória para demonstração (foco é auth, não persistência)
DOCUMENTS_DB: list[dict] = [
    {
        "id": 1,
        "title": "Relatório de Arquitetura",
        "content": "Documento confidencial de arquitetura de sistemas distribuídos.",
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


# ── GET /documents ─────────────────────────────────────────────────────────────

@router.get(
    "/documents",
    response_model=list[DocumentResponse],
    responses=_AUTH_RESPONSES,
    summary="Listar documentos (validação local via JWKS)",
)
async def list_documents(
    current_user: dict = Depends(get_current_user),
):
    """
    Lista documentos com filtro por role usando **validação local via JWKS**.
    - **admin**  → retorna TODOS os documentos
    - **editor** → retorna apenas os documentos cujo `owner_id == sub` do token
    - **viewer** → idem editor

    > 401 se sem token ou token inválido · 403 nunca ocorre aqui (qualquer role acessa)
    """
    if has_role(current_user, "admin"):
        return DOCUMENTS_DB

    user_sub = current_user["sub"]
    return [d for d in DOCUMENTS_DB if d["owner_id"] == user_sub]


# ── GET /documents-introspect (Card 24) ───────────────────────────────────────

@router.get(
    "/documents-introspect",
    response_model=list[DocumentResponse],
    responses={
        **_AUTH_RESPONSES,
        503: {"model": ErrorResponse, "description": "Keycloak inacessível para Token Introspection."},
    },
    summary="Listar documentos (validação remota via Token Introspection RFC 7662)",
)
async def list_documents_introspect(
    current_user: dict = Depends(get_current_user_introspect),
):
    """
    Lista documentos com filtro por role usando **Token Introspection (RFC 7662)**.

    Diferença vs GET /documents:
    - **GET /documents**: valida localmente via JWKS em memória (< 5ms).
    - **GET /documents-introspect**: consulta o Keycloak via POST /token/introspect a cada requisição.
      Permite revogação instantânea de sessão ao custo de uma chamada HTTP adicional por request.
    """
    if has_role(current_user, "admin"):
        return DOCUMENTS_DB

    user_sub = current_user["sub"]
    return [d for d in DOCUMENTS_DB if d["owner_id"] == user_sub]


# ── POST /documents ─────────────────────────────────────────────────────────────

@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_AUTH_RESPONSES,
    summary="Criar documento (editor ou admin com scope documents:write)",
)
async def create_document(
    doc: DocumentCreate,
    current_user: dict = Depends(require_roles("admin", "editor")),
    _: dict = Depends(require_scopes("documents:write")),
):
    """
    Cria documento. Requer role **editor** ou **admin** E scope **documents:write**.

    - `owner_id` é preenchido automaticamente com o `sub` do JWT (não enviado no body).
    - **viewer** recebe `403 Forbidden` (role insuficiente).
    - Cliente sem scope **documents:write** recebe `403 Forbidden` (scope insuficiente).

    > 401 se sem token ou token inválido · 403 se role for viewer ou faltar scope documents:write
    """
    global _next_id
    new_doc = {
        "id": _next_id,
        "title": doc.title,
        "content": doc.content,
        "owner_id": current_user["sub"],
    }
    _next_id += 1
    DOCUMENTS_DB.append(new_doc)
    return new_doc


# ── GET /documents/{id} ─────────────────────────────────────────────────────────

@router.get(
    "/documents/{doc_id}",
    response_model=DocumentResponse,
    responses={
        **_AUTH_RESPONSES,
        404: {"model": ErrorResponse, "description": "Documento não encontrado."},
    },
    summary="Buscar documento por ID",
)
async def get_document(
    doc_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Busca documento por ID.
    - **admin**  → acessa qualquer documento
    - **editor** → acessa apenas documentos próprios (`403` se não for dono)
    - **viewer** → idem editor

    > 401 se sem token ou token inválido · 403 se editor/viewer acessar doc alheio · 404 se não existir
    """
    doc = next((d for d in DOCUMENTS_DB if d["id"] == doc_id), None)

    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento {doc_id} não encontrado.",
        )

    if has_role(current_user, "admin"):
        return doc

    if doc["owner_id"] != current_user["sub"]:
        username = current_user.get("preferred_username", "?")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Acesso negado para '{username}'. "
                "Este documento pertence a outro usuário."
            ),
        )

    return doc


# ── DELETE /documents/{id} ─────────────────────────────────────────────────────

@router.delete(
    "/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **_AUTH_RESPONSES,
        404: {"model": ErrorResponse, "description": "Documento não encontrado."},
    },
    summary="Remover documento (somente admin)",
)
async def delete_document(
    doc_id: int,
    current_user: dict = Depends(require_roles("admin")),
):
    """
    Remove documento. Requer role **admin**.

    - **editor** e **viewer** recebem `403 Forbidden`.

    > 401 se sem token ou token inválido · 403 se não for admin · 404 se não existir
    """
    for idx, d in enumerate(DOCUMENTS_DB):
        if d["id"] == doc_id:
            DOCUMENTS_DB.pop(idx)
            return

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Documento {doc_id} não encontrado.",
    )


# ── GET /me ────────────────────────────────────────────────────────────────────

@router.get(
    "/me",
    responses={
        401: _AUTH_RESPONSES[401],
    },
    summary="Inspecionar token (claims do JWT atual)",
)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Retorna os claims relevantes do JWT do usuário autenticado.

    Útil para verificar qual `sub`, quais `roles`, quais `scopes` e qual `email` estão no token.

    > 401 se sem token ou token inválido · nunca retorna 403 (qualquer autenticado acessa)
    """
    roles = current_user.get("realm_access", {}).get("roles", [])
    scopes = extract_scopes(current_user)
    return {
        "sub": current_user.get("sub"),
        "username": current_user.get("preferred_username"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "roles": roles,
        "scopes": scopes,
        "token_expires_at": current_user.get("exp"),
        "issued_by": current_user.get("iss"),
    }
