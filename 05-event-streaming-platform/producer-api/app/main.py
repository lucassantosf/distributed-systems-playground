"""
Aplicação FastAPI — Producer API
Event Streaming Platform — 05
"""

import logging

from fastapi import FastAPI

from app.api.orders import router as orders_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Producer API",
    description="Recebe pedidos via HTTP, persiste no PostgreSQL e publica eventos no Kafka.",
    version="1.0.0",
)

app.include_router(orders_router)


@app.get("/health", tags=["infra"])
def health():
    """Healthcheck para o Docker Compose e monitoramento."""
    return {"status": "ok", "service": "producer-api"}
