from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
    Formato padrão de erro da API.

    Todos os erros HTTP (401, 403, 404, 422, 503) retornam este schema.

    Distinção semântica:
      HTTP 401 Unauthorized → "Não sei quem você é"
                              Token ausente, malformado ou expirado.
                              Sempre inclui o header: WWW-Authenticate: Bearer

      HTTP 403 Forbidden    → "Sei quem você é, mas não pode fazer isso"
                              Token válido, porém o usuário não tem a role
                              necessária ou não é dono do recurso solicitado.

      HTTP 404 Not Found    → Recurso não encontrado.

      HTTP 422 Unprocessable Entity → Payload inválido (campos ausentes/errados).

      HTTP 503 Service Unavailable  → Keycloak inacessível ao buscar JWKS.
    """

    detail: str = Field(
        ...,
        description=(
            "Mensagem explicando o motivo do erro. "
            "Exemplos: 'Token de autenticação não fornecido', "
            "'Acesso negado para carol. Roles necessárias: [admin]'."
        ),
        examples=["Token de autenticação não fornecido. Inclua o header: Authorization: Bearer <token>"],
    )
