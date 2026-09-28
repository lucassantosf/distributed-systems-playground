from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    """
    Payload para criar um documento.
    O owner_id NÃO é enviado pelo cliente — é extraído do sub do JWT (Card 6).
    """
    title: str = Field(..., description="Título do documento")
    content: str = Field(..., description="Conteúdo do documento")

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Relatório de Vendas Q1",
                "content": "Análise detalhada das vendas do primeiro trimestre.",
            }
        }
    }


class DocumentResponse(BaseModel):
    id: int = Field(..., description="ID sequencial único do documento")
    title: str = Field(..., description="Título do documento")
    content: str = Field(..., description="Conteúdo do documento")
    owner_id: str = Field(..., description="sub (UUID) do proprietário no Keycloak")
