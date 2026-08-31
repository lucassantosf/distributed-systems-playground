# =============================================================================
# sample-app — Endpoint de Debug para geração de logs e simulação de alertas
# Card 11: gera logs INFO, WARNING e ERROR
# Card 14: endpoints /debug/error (500) e /debug/slow (600ms) para testar alertas
# =============================================================================
import asyncio
import random

from fastapi import APIRouter, HTTPException

from app.logging_config import setup_logging

log = setup_logging()

router = APIRouter(prefix="/debug", tags=["debug"])


@router.post("/generate-logs", summary="Gera logs de diferentes níveis para teste")
async def generate_logs() -> dict:
    """
    Gera logs de INFO, WARNING e ERROR para popular o dashboard de logs do Card 11.
    """
    info_count = random.randint(3, 6)

    for i in range(info_count):
        await asyncio.sleep(0.01)
        log.info("Log INFO de teste #%d via /debug/generate-logs", i + 1)

    log.warning(
        "Processamento lento detectado — latência acima de 500ms (WARNING de teste via /debug/generate-logs)"
    )

    log.error(
        "Falha ao processar operação crítica — erro simulado via /debug/generate-logs "
        "(não é um erro real da aplicação)"
    )

    return {
        "logs_gerados": {
            "INFO": info_count,
            "WARNING": 1,
            "ERROR": 1,
        },
        "total": info_count + 2,
        "note": "Logs enviados para OpenSearch via Filebeat → Logstash",
    }


@router.get("/error", summary="Força um erro 500 para testar o alerta HighErrorRate")
async def force_error() -> dict:
    """
    Retorna 500 Internal Server Error para elevar a taxa de erros 5xx.
    """
    log.error("Simulando falha 500 Internal Server Error em /debug/error")
    raise HTTPException(status_code=500, detail="Erro 500 simulado para teste de alerta")


@router.get("/slow", summary="Força uma latência de 600ms para testar o alerta HighLatency")
async def force_slow() -> dict:
    """
    Aguarda 0.6s para elevar o percentil P95 de latência da aplicação.
    """
    log.warning("Simulando rota lenta de 600ms em /debug/slow")
    await asyncio.sleep(0.6)
    return {"status": "slow_response", "delay_ms": 600}
