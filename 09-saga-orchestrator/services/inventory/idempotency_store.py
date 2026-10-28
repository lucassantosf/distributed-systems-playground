"""
Idempotency Store — Card 6.2: Serviços Mockados Idempotentes.

Mantém um dicionário em memória {command_id: reply_payload} para evitar
re-execução da lógica de negócio quando um mesmo command_id chega mais de
uma vez (ex: retry do orquestrador antes de receber a resposta anterior).

Simula o comportamento de serviços reais com suporte a idempotency-key,
como gateways de pagamento ou APIs de envio de e-mail.

IMPORTANTE: este store é em memória (dicionário Python). Em produção real,
usaria Redis, banco de dados ou outro backend durável para sobreviver a
reinicializações do serviço.
"""
import logging
from typing import Any, Optional

logger = logging.getLogger("idempotency-store")

# Dicionário em memória: {command_id: reply_payload}
# Cada worker tem sua própria instância isolada ao importar este módulo.
_store: dict[str, dict[str, Any]] = {}


def get(command_id: str) -> Optional[dict[str, Any]]:
    """
    Retorna o reply cacheado para o command_id, ou None se não visto antes.
    """
    cached = _store.get(command_id)
    if cached is not None:
        logger.info(
            f"[Idempotency] command_id={command_id} já processado — "
            f"retornando resultado cacheado sem re-executar lógica de negócio."
        )
    return cached


def save(command_id: str, reply_payload: dict[str, Any]) -> None:
    """
    Persiste o reply do command_id para uso em chamadas futuras duplicadas.
    """
    _store[command_id] = reply_payload
    logger.debug(f"[Idempotency] Resultado salvo para command_id={command_id}.")


def size() -> int:
    """Retorna quantos command_ids estão cacheados (útil para testes/métricas)."""
    return len(_store)


def clear() -> None:
    """
    Limpa todo o store. Usar apenas em testes — nunca em produção,
    pois eliminaria a proteção contra duplicatas.
    """
    _store.clear()

