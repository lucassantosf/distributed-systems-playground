from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes.health import router as health_router
from src.settings import settings
from src.api.routes.orders import router as orders_router

from src.infrastructure.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # initialize DB tables in development so the mapped models exist
    if settings.ENVIRONMENT == "development":
        init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

    app.include_router(health_router, tags=["health"])
    app.include_router(orders_router, tags=["orders"])

    return app


app = create_app()
