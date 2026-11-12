import logging

from fastapi import FastAPI

from src.presentation.api.routes import chat, health, repos

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Software Engineering Assistant",
        description="Plataforma de análise de repositórios de código via RAG + LLM.",
        version="0.1.0",
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(repos.router)
    app.include_router(chat.router)

    return app


app = create_app()

