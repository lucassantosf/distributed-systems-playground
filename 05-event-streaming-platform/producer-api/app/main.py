"""
Aplicação FastAPI — Producer API
Event Streaming Platform — 05
"""

import logging
import time

from fastapi import FastAPI, Request, Response

from app.api.orders import router as orders_router
from app.telemetry import setup_tracing          # Card 18.1
from app.logging_config import setup_logging     # Card 18.2
from app.metrics import (                        # Card 18.3
    get_metrics_app,
    http_requests_total,
    http_request_duration_seconds,
)

# Card 18.2 — Inicializa logging JSON estruturado com trace_id
logger = setup_logging()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Producer API",
    description="Recebe pedidos via HTTP, persiste no PostgreSQL e publica eventos no Kafka.",
    version="1.0.0",
)

# Card 18.1 — Inicializa OTel TracerProvider e instrumenta o FastAPI
setup_tracing(app)

# Card 18.3 — Monta /metrics (ASGI sub-app do prometheus_client)
app.mount("/metrics", get_metrics_app())

app.include_router(orders_router)


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next) -> Response:
    """
    Card 18.3 — Middleware que instrumenta todas as requisições HTTP:
    - http_requests_total       (método, rota normalizada, status HTTP)
    - http_request_duration_seconds (método, rota normalizada)
    """
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    route = request.scope.get("route")
    endpoint = route.path if route else request.url.path
    method = request.method
    status = str(response.status_code)

    http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
    http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

    return response


@app.get("/health", tags=["infra"])
def health():
    """Healthcheck para o Docker Compose e monitoramento."""
    return {"status": "ok", "service": "producer-api"}
