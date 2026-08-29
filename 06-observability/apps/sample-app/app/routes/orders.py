# =============================================================================
# sample-app — Router de Pedidos (Orders)
# Card 6 : GET /orders + POST /orders com delay aleatório para simular latência
# Card 7 : Decorado com métricas Prometheus
# Card 8 : Spans filhos para simular operações internas
# =============================================================================
import asyncio
import random
import uuid
from datetime import datetime

from fastapi import APIRouter

from app.logging_config import setup_logging
from app.metrics import app_orders_created_total

log = setup_logging()

router = APIRouter(prefix="/orders", tags=["orders"])

# Banco de dados simulado em memória
_orders: list[dict] = []


@router.get("")
async def list_orders() -> dict:
    """
    Retorna a lista de pedidos cadastrados.
    Card 7: incrementar http_requests_total e medir duração (via middleware).
    Card 8: criar span filho "db_query".
    """
    log.info("GET /orders — listando %d pedidos", len(_orders))

    # Card 8: com traces, este bloco vira um span filho
    await asyncio.sleep(random.uniform(0.005, 0.015))  # simula latência de DB

    return {"orders": _orders, "total": len(_orders)}


@router.post("", status_code=201)
async def create_order(body: dict) -> dict:
    """
    Cria um novo pedido com delay aleatório para simular variação de latência.
    Card 7: incrementar http_requests_total, medir duração e app_orders_created_total.
    Card 8: criar spans filhos "validate_order" e "process_order".
    """
    order_id = str(uuid.uuid4())[:8]
    item = body.get("item", "unknown")

    log.info("POST /orders — recebendo pedido: item=%s", item)

    # Card 8: com traces, cada await vira um span filho separado
    # ── Simula validação (rápida) ──────────────────────────────────
    await asyncio.sleep(random.uniform(0.01, 0.05))
    log.debug("Pedido %s validado", order_id)

    # ── Simula processamento (variação grande de latência) ─────────
    delay = random.uniform(0.05, 0.5)
    await asyncio.sleep(delay)
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
