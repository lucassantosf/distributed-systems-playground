from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    """
    Payload para criação de documento via BFF.
    O owner_id não é enviado pelo cliente — é extraído do sub do token JWT do usuário autenticado.
    """
    title: str = Field(..., description="Título do documento")
    content: str = Field(..., description="Conteúdo do documento")

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Relatório de Arquitetura BFF",
                "content": "Detalhes de comunicação entre BFF e serviços internos.",
            }
        }
    }


class DocumentResponse(BaseModel):
    id: int = Field(..., description="ID sequencial único do documento")
    title: str = Field(..., description="Título do documento")
    content: str = Field(..., description="Conteúdo do documento")
    owner_id: str = Field(..., description="sub (UUID) do proprietário no Keycloak")
