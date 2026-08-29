# =============================================================================
# sample-app — Entry point FastAPI
#
# Card 6 : FastAPI base com /health e router de orders
# Card 7  : /metrics + middleware de instrumentação Prometheus ✅
# Card 8  : Chamar setup_tracing(app) para auto-instrumentação OTel
# Card 9  : Atualizar logging_config.py para emitir JSON com trace_id/span_id
# =============================================================================
import time

from fastapi import FastAPI, Request, Response

from app.config import APP_NAME, APP_ENV
from app.logging_config import setup_logging
from app.metrics import get_metrics_app, http_requests_total, http_request_duration_seconds
from app.routes.orders import router as orders_router

# ── Card 8: descomentar ────────────────────────────────────────────────────────
# from app.telemetry import setup_tracing

log = setup_logging()

app = FastAPI(
    title=APP_NAME,
    description="Aplicação de exemplo para plataforma de observabilidade",
    version="1.0.0",
)

# ── Card 8: inicializar tracing ANTES dos routers ──────────────────────────────
# setup_tracing(app)

# ── Card 7: montar /metrics (ASGI sub-app do prometheus_client) ────────────────
app.mount("/metrics", get_metrics_app())

# Routers
app.include_router(orders_router)


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next) -> Response:
    """
    Middleware que instrumenta automaticamente todas as requisições:
    - http_requests_total (método, rota normalizada, status HTTP)
    - http_request_duration_seconds (método, rota normalizada)

    Usa request.scope["path"] para normalizar rotas como /orders/123 → /orders/{id}
    quando FastAPI resolver os path params (via route.path).
    """
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    # Tenta obter a rota normalizada pelo FastAPI (ex: /orders ao invés de /orders/)
    route = request.scope.get("route")
    endpoint = route.path if route else request.url.path

    method = request.method
    status = str(response.status_code)

    http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
    http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

    return response


@app.get("/health", tags=["infra"])
async def health() -> dict:
    """Endpoint de saúde da aplicação — usado por healthchecks e Prometheus."""
    return {"status": "ok", "service": APP_NAME, "env": APP_ENV}


@app.on_event("startup")
async def on_startup() -> None:
    log.info("=== %s iniciando | env=%s ===", APP_NAME, APP_ENV)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    log.info("=== %s encerrando ===", APP_NAME)
