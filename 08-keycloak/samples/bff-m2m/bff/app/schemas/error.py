from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
    Formato padrão de resposta de erro da API do BFF.

    Semântica HTTP:
      - 401 Unauthorized: Token ausente, expirado ou com assinatura inválida.
      - 403 Forbidden: Token válido, mas permissão insuficiente (RBAC).
      - 404 Not Found: Recurso não encontrado.
      - 422 Unprocessable Entity: Payload inválido ou campos ausentes.
      - 502 Bad Gateway: Falha de comunicação com serviço downstream.
      - 503 Service Unavailable: Keycloak inacessível para obtenção do JWKS.
    """

    detail: str = Field(
        ...,
        description="Mensagem descritiva do erro ocorrido.",
        examples=["Token de autenticação não fornecido. Inclua o header: Authorization: Bearer <token>"],
    )
