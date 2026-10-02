"""
docs-service/app/routers/internal.py — Card 18: Rotas internas (sem auth por enquanto)

Expõe /internal/* exclusivamente para o BFF.
Por enquanto retorna dados de exemplo em memória.
A validação do token de serviço será adicionada no Card 21.
"""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/internal", tags=["Internal"])

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
    summary="[INTERNO] Listar todos os documentos",
    description=(
        "Endpoint acessível **apenas pelo BFF**. Não é exposto diretamente ao usuário.\n\n"
        "Card 18: Sem autenticação (dados em memória).\n"
        "Card 21: Validará que o chamador é o `bff-client` autorizado via token de serviço."
    ),
)
async def list_documents():
    return {
        "source": "docs-service (dados em memória — Card 18)",
        "documents": DOCUMENTS_DB,
    }


@router.get("/documents/{doc_id}", summary="[INTERNO] Buscar documento por ID")
async def get_document(doc_id: int):
    doc = next((d for d in DOCUMENTS_DB if d["id"] == doc_id), None)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento {doc_id} não encontrado.",
        )
    return {"source": "docs-service (dados em memória — Card 18)", "document": doc}
