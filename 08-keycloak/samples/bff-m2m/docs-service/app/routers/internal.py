"""
docs-service/app/routers/internal.py — Card 21: Endpoints internos com validação M2M

Todos os endpoints requerem um token de serviço válido emitido pelo bff-client via
Client Credentials. Chamadas diretas de usuários (com tokens de usuário) são recusadas
com 403 Forbidden, mesmo que o token seja tecnicamente válido.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_service_caller
from app.schemas.error import ErrorResponse

router = APIRouter(prefix="/internal", tags=["Internal"])

# ── Respostas documentadas para OpenAPI ───────────────────────────────────────
_SERVICE_AUTH_RESPONSES = {
    401: {
        "model": ErrorResponse,
        "description": (
            "**401 Unauthorized** — Token de serviço ausente ou inválido.\n\n"
            "Este endpoint é interno e requer autenticação M2M via Client Credentials."
        ),
    },
    403: {
        "model": ErrorResponse,
        "description": (
            "**403 Forbidden** — Token válido, mas o chamador não é o `bff-client` autorizado.\n\n"
            "Chamadas diretas de usuários humanos (com tokens de usuário) são rejeitadas aqui, "
            "demonstrando o isolamento entre a camada pública (BFF) e a camada interna (docs-service)."
        ),
    },
}

# Dados em memória do serviço de documentos
DOCUMENTS_DB: list[dict] = [
    {
        "id": 1,
        "title": "Relatório de Arquitetura",
        "content": "Documento de arquitetura de sistemas distribuídos.",
        "owner_id": "5d0cca8a-69f3-45de-9620-19ae469f06e9",  # alice
    },
    {
        "id": 2,
        "title": "Proposta de Projeto",
        "content": "Rascunho da proposta comercial para o cliente X.",
        "owner_id": "e5fdac7a-c5e2-4945-aa9f-aeba150d897a",  # bob
    },
    {
        "id": 3,
        "title": "Guia de Boas Práticas",
        "content": "Instruções para revisão de código, padrões e testes.",
        "owner_id": "8c02af90-09e9-4d22-870a-72df2d19aecb",  # carol
    },
]


@router.get(
    "/documents",
    responses=_SERVICE_AUTH_RESPONSES,
    summary="[INTERNO] Listar documentos — apenas bff-client via M2M",
)
async def list_documents(
    service_caller: dict = Depends(get_service_caller),
):
    """
    Retorna todos os documentos. Exige token de serviço do bff-client (azp=bff-client).
    O docs-service não aplica RBAC por usuário — isso é responsabilidade do BFF.
    Chamadas diretas sem token (ou com token de usuário humano) são rejeitadas.
    """
    return {
        "source": "docs-service",
        "caller": service_caller.get("azp"),
        "documents": DOCUMENTS_DB,
    }


@router.get(
    "/documents/{doc_id}",
    responses={
        **_SERVICE_AUTH_RESPONSES,
        404: {"model": ErrorResponse, "description": "Documento não encontrado."},
    },
    summary="[INTERNO] Buscar documento por ID — apenas bff-client via M2M",
)
async def get_document(
    doc_id: int,
    service_caller: dict = Depends(get_service_caller),
):
    """
    Busca um documento por ID. Exige token de serviço do bff-client (azp=bff-client).
    """
    doc = next((d for d in DOCUMENTS_DB if d["id"] == doc_id), None)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento {doc_id} não encontrado.",
        )
    return {
        "source": "docs-service",
        "caller": service_caller.get("azp"),
        "document": doc,
    }
