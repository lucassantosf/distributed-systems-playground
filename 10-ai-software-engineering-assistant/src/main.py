from fastapi import FastAPI

from src.presentation.api.routes import health


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Software Engineering Assistant",
        description="Plataforma de análise de repositórios de código via RAG + LLM.",
        version="0.1.0",
    )

    app.include_router(health.router, tags=["health"])

    return app


app = create_app()

