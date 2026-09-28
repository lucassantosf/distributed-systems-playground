from fastapi import FastAPI
from app.routers import documents

app = FastAPI(
    title="Sample A — API Simples",
    description="FastAPI para demonstração de autenticação e autorização via Keycloak",
    version="1.0.0",
)

app.include_router(documents.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "api-simples"}
