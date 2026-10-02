from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers import bff as bff_router

app = FastAPI(
    title="BFF — Backend for Frontend",
    description=(
        "Intermediário entre o Frontend (usuário externo) e o docs-service (serviço interno).\n\n"
        "## Responsabilidades\n"
        "- Valida o token JWT do **usuário** que chama `/bff/*` via JWKS do Keycloak (Card 19).\n"
        "- Aplica controle de acesso baseado em roles (RBAC: admin / editor / viewer).\n"
        "- Obtém um **token de serviço** próprio via Client Credentials para chamar o docs-service (Card 20).\n"
        "- O usuário final nunca se comunica diretamente com o docs-service.\n\n"
        "## Semântica de erros\n"
        "| Código | Quando |\n"
        "|--------|--------|\n"
        "| 401 | Token do usuário ausente, malformado ou expirado |\n"
        "| 403 | Token válido, mas role insuficiente para a ação |\n"
        "| 404 | Recurso não encontrado |\n"
        "| 422 | Payload de requisição inválido ou campos ausentes |\n"
        "| 502 | Falha ao comunicar com o docs-service |\n"
        "| 503 | Keycloak inacessível ao obter JWKS ou token de serviço |\n\n"
        "Todos os erros retornam `{\"detail\": \"<mensagem explicativa>\"}`."
    ),
    version="1.0.0",
)

app.include_router(bff_router.router)


# ── Formatação customizada de erro 422 ────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Formata erros de validação de payload (422) de forma legível e consistente.
    """
    missing = []
    invalid = []

    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", []) if x != "body"]
        field = " -> ".join(loc) if loc else "desconhecido"

        if err.get("type") == "missing":
            missing.append(field)
        else:
            invalid.append(f"{field}: {err.get('msg', 'valor inválido')}")

    parts = []
    if missing:
        parts.append(f"Campos obrigatórios ausentes: {', '.join(missing)}")
    if invalid:
        parts.append(f"Campos com valor inválido: {'; '.join(invalid)}")

    detail = ". ".join(parts) if parts else "Payload inválido."

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": detail},
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "service": "bff"}
