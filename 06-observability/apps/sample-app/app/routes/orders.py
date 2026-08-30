# =============================================================================
# sample-app — Router de Pedidos (Orders)
# Card 6 : GET /orders + POST /orders com delay aleatório para simular latência
# Card 7 : Métricas Prometheus via middleware (http_requests_total, duração) ✅
#          + app_orders_created_total.inc() ✅
# Card 8 : Spans filhos para simular operações internas ✅
# =============================================================================
import asyncio
import random
import uuid
from datetime import datetime

from fastapi import APIRouter

from app.logging_config import setup_logging
from app.metrics import app_orders_created_total
from app.telemetry import get_tracer

log = setup_logging()
tracer = get_tracer()

router = APIRouter(prefix="/orders", tags=["orders"])

# Banco de dados simulado em memória
_orders: list[dict] = []


@router.get("")
async def list_orders() -> dict:
    """
    Retorna a lista de pedidos.
    Card 8: span filho "db.query" simulando leitura no banco.
    """
    log.info("GET /orders — listando %d pedidos", len(_orders))

    # Span filho: simula uma consulta ao banco de dados
    with tracer.start_as_current_span("db.query") as span:
        span.set_attribute("db.system", "in-memory")
        span.set_attribute("db.operation", "SELECT")
        span.set_attribute("db.statement", "SELECT * FROM orders")
        span.set_attribute("db.result_count", len(_orders))

        await asyncio.sleep(random.uniform(0.005, 0.015))  # simula latência de DB

    return {"orders": _orders, "total": len(_orders)}


@router.post("", status_code=201)
async def create_order(body: dict) -> dict:
    """
    Cria um novo pedido com delay aleatório para simular variação de latência.
    Card 8: spans filhos "order.validate" e "order.process".
    """
    order_id = str(uuid.uuid4())[:8]
    item = body.get("item", "unknown")

    log.info("POST /orders — recebendo pedido: item=%s", item)

    # Span filho 1: simula validação do pedido
    with tracer.start_as_current_span("order.validate") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("order.item", item)
        await asyncio.sleep(random.uniform(0.01, 0.05))
        log.debug("Pedido %s validado", order_id)

    # Span filho 2: simula processamento (variação grande de latência)
    with tracer.start_as_current_span("order.process") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("order.item", item)
        delay = random.uniform(0.05, 0.5)
        await asyncio.sleep(delay)
        span.set_attribute("order.processing_time_ms", round(delay * 1000, 1))
        log.debug("Pedido %s processado em %.3fs", order_id, delay)

    order = {
        "id": order_id,
        "item": item,
        "status": "created",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "processing_time_ms": round(delay * 1000, 1),
    }
    _orders.append(order)

    # Card 7: Incrementar contador de pedidos criados
    app_orders_created_total.inc()

    log.info("POST /orders — pedido criado: id=%s item=%s", order_id, item)
    return order
