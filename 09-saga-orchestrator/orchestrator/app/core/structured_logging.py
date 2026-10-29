"""
Módulo de Logging Estruturado em JSON — Card 7.4.

Emite logs no formato JSON com os campos contextuais da Saga:
  - saga_id: UUID da Saga em execução
  - step_name: nome do step atual (ex: ReservarEstoque)
  - command_id: identificador único da tentativa (idempotency key)
  - attempt: número da tentativa atual

Utiliza contextvars.ContextVar (PEP 567) para propagação assíncrona
segura através de corrotinas asyncio sem poluir as assinaturas de função.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional

# ContextVars para propagação contextual assíncrona
saga_id_var: ContextVar[Optional[str]] = ContextVar("saga_id", default=None)
step_name_var: ContextVar[Optional[str]] = ContextVar("step_name", default=None)
command_id_var: ContextVar[Optional[str]] = ContextVar("command_id", default=None)
attempt_var: ContextVar[Optional[int]] = ContextVar("attempt", default=None)


def set_saga_context(
    saga_id: Optional[str] = None,
    step_name: Optional[str] = None,
    command_id: Optional[str] = None,
    attempt: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Define variáveis no contexto da Saga atual e retorna tokens para posterior reset.
    """
    tokens = {}
    if saga_id is not None:
        tokens["saga_id"] = saga_id_var.set(str(saga_id))
    if step_name is not None:
        tokens["step_name"] = step_name_var.set(str(step_name))
    if command_id is not None:
        tokens["command_id"] = command_id_var.set(str(command_id))
    if attempt is not None:
        tokens["attempt"] = attempt_var.set(int(attempt))
    return tokens


def clear_saga_context() -> None:
    """Limpa todos os campos contextuais da Saga no contexto atual."""
    saga_id_var.set(None)
    step_name_var.set(None)
    command_id_var.set(None)
    attempt_var.set(None)


def get_saga_context() -> Dict[str, Any]:
    """Retorna um dicionário com o contexto atual da Saga."""
    return {
        "saga_id": saga_id_var.get(),
        "step_name": step_name_var.get(),
        "command_id": command_id_var.get(),
        "attempt": attempt_var.get(),
    }


@contextmanager
def saga_context(
    saga_id: Optional[str] = None,
    step_name: Optional[str] = None,
    command_id: Optional[str] = None,
    attempt: Optional[int] = None,
):
    """
    Context manager síncrono/assíncrono para delimitar o escopo de uma Saga.
    Restaura automaticamente os valores anteriores ao sair do bloco with.
    """
    tokens = set_saga_context(
        saga_id=saga_id,
        step_name=step_name,
        command_id=command_id,
        attempt=attempt,
    )
    try:
        yield
    finally:
        for var_name, token in tokens.items():
            if var_name == "saga_id":
                saga_id_var.reset(token)
            elif var_name == "step_name":
                step_name_var.reset(token)
            elif var_name == "command_id":
                command_id_var.reset(token)
            elif var_name == "attempt":
                attempt_var.reset(token)


class JSONFormatter(logging.Formatter):
    """
    Formatador de log estruturado que serializa cada LogRecord como JSON (Card 7.4).
    Garante a inclusão de saga_id, step_name, command_id e attempt em todas as linhas.
    """

    def format(self, record: logging.LogRecord) -> str:
        ctx = get_saga_context()

        # Determina os valores prioritariamente do record (se passados via extra) ou do contextvar
        saga_id = getattr(record, "saga_id", None) or ctx["saga_id"]
        step_name = getattr(record, "step_name", None) or ctx["step_name"]
        command_id = getattr(record, "command_id", None) or ctx["command_id"]
        attempt = getattr(record, "attempt", None) or ctx["attempt"]

        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "saga_id": saga_id,
            "step_name": step_name,
            "command_id": command_id,
            "attempt": attempt,
        }

        # Trata exceções com traceback formatado
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def setup_structured_logging(level: int = logging.INFO) -> None:
    """Configura o root logger para emitir JSON estruturado no stdout."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [handler]

