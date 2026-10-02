from fastapi import FastAPI

app = FastAPI(
    title="docs-service — Serviço Interno de Documentos",
    description=(
        "Serviço **downstream** que expõe endpoints em `/internal/*`.\n\n"
        "## Isolamento\n"
        "Este serviço **não é acessível diretamente** pelo usuário final.\n"
        "Apenas o BFF (que possui um token de serviço válido via Client Credentials) pode chamá-lo.\n\n"
        "A partir do Card 21, o docs-service validará que o chamador é o `bff-client` autorizado,\n"
        "recusando qualquer chamada direta — inclusive de usuários com token válido.\n\n"
        "## Semântica de erros\n"
        "| Código | Quando |\n"
        "|--------|--------|\n"
        "| 401 | Token de serviço ausente ou inválido |\n"
        "| 403 | Token válido mas não é do bff-client |\n"
        "| 404 | Documento não encontrado |"
    ),
    version="1.0.0",
)

from app.routers import internal as internal_router  # noqa: E402
app.include_router(internal_router.router)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "service": "docs-service"}
