from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.routers import documents

app = FastAPI(
    title="Sample A — API Simples",
    description=(
        "FastAPI protegida por JWT Keycloak demonstrando autenticação e autorização.\n\n"
        "## Semântica de erros\n\n"
        "| Código | Significado | Quando ocorre |\n"
        "|--------|-------------|---------------|\n"
        "| **401** | *Não sei quem você é* | Token ausente, malformado ou expirado |\n"
        "| **403** | *Sei quem você é, mas não pode* | Role insuficiente ou recurso de outro usuário |\n"
        "| **404** | Não encontrado | Documento com o ID solicitado não existe |\n"
        "| **422** | Payload inválido | Campo obrigatório ausente ou tipo errado |\n"
        "| **503** | Serviço indisponível | Keycloak inacessível ao buscar JWKS |\n\n"
        "Todos os erros retornam `{\"detail\": \"<mensagem explicativa>\"}` no body."
    ),
    version="1.0.0",
)

app.include_router(documents.router)


# ── Handlers de erro ──────────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Formata erros de validação de payload (422) de forma legível.

    Transforma a lista aninhada do Pydantic em uma mensagem `detail` clara,
    mantendo o mesmo formato {detail: "..."} dos demais erros da API.
    """
    missing = []
    invalid = []

    for err in exc.errors():
        # Remove "body" da localização para mostrar só o nome do campo
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
    return {"status": "ok", "service": "api-simples"}
