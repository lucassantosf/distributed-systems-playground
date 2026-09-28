from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.schemas.document import DocumentCreate, DocumentResponse

router = APIRouter()

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


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    current_user: dict = Depends(get_current_user),
):
    """
    Lista documentos. Requer autenticação.
    Card 6: todos os documentos são retornados para qualquer usuário autenticado.
    Card 7 vai filtrar por role (admin vê todos; editor/viewer veem apenas os próprios).
    """
    return DOCUMENTS_DB


@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    doc: DocumentCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Cria documento. owner_id é preenchido automaticamente via sub do JWT.
    Card 7 vai restringir este endpoint a roles editor/admin.
    """
    global _next_id
    new_doc = {
        "id": _next_id,
        "title": doc.title,
        "content": doc.content,
        "owner_id": current_user["sub"],  # Sub do JWT = ID único do usuário
    }
    _next_id += 1
    DOCUMENTS_DB.append(new_doc)
    return new_doc


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Busca documento por ID. Requer autenticação.
    Card 7 vai restringir: não-admin só acessa documentos próprios.
    """
    for d in DOCUMENTS_DB:
        if d["id"] == doc_id:
            return d
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Remove documento. Requer autenticação.
    Card 7 vai restringir este endpoint a role admin.
    """
    for idx, d in enumerate(DOCUMENTS_DB):
        if d["id"] == doc_id:
            DOCUMENTS_DB.pop(idx)
            return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Retorna os claims do token JWT do usuário autenticado.
    Útil para debugar e entender o que o token contém.
    """
    roles = current_user.get("realm_access", {}).get("roles", [])
    return {
        "sub": current_user.get("sub"),
        "username": current_user.get("preferred_username"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "roles": roles,
        "token_expires_at": current_user.get("exp"),
        "issued_by": current_user.get("iss"),
    }
