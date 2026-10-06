from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
    Formato padrão de resposta de erro do docs-service.

    Semântica HTTP:
      - 401 Unauthorized: Token de serviço ausente, expirado ou com assinatura inválida.
      - 403 Forbidden: Token válido, mas o chamador não é o bff-client autorizado (azp inválido).
      - 404 Not Found: Documento não encontrado.
      - 503 Service Unavailable: Keycloak inacessível para obtenção do JWKS.
    """

    detail: str = Field(
        ...,
        description="Mensagem descritiva do erro ocorrido.",
        examples=["Token de serviço não fornecido. Este endpoint é interno e só pode ser chamado pelo BFF via M2M."],
    )
