# =============================================================================
# sample-app — Configuração de logging
# Card 6 : Logging padrão Python → arquivo + console
# Card 9 : JSON estruturado com trace_id/span_id injetados do OTel ✅
# =============================================================================
import logging
import logging.handlers
import os
import sys

from pythonjsonlogger import jsonlogger
from opentelemetry import trace

from app.config import LOG_FILE, LOG_DIR, APP_NAME


class OtelTraceFilter(logging.Filter):
    """
    Filter que injeta trace_id e span_id do OpenTelemetry em cada log record.

    Quando o log é emitido dentro de um Span ativo (ex: dentro de um handler
    FastAPI instrumentado), os IDs são extraídos do contexto OTel e adicionados
    como campos no log. Quando não há span ativo, os campos ficam como ''.

    Esse mecanismo é o que permite no Grafana clicar em um trace e navegar
    diretamente até os logs correspondentes via Data Link (Card 10+).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        span = trace.get_current_span()
        ctx = span.get_span_context()

        if ctx.is_valid:
            # Formata como string hexadecimal de 32 chars (padrão W3C TraceContext)
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        else:
            record.trace_id = ""
            record.span_id = ""

        return True


def setup_logging() -> logging.Logger:
    """
    Configura o logger da aplicação em modo JSON estruturado.

    Cada linha de log é um objeto JSON com os campos:
      timestamp, level, message, service, trace_id, span_id

    Usa um guarda (hasHandlers) para evitar duplicação de handlers caso
    setup_logging() seja chamado em múltiplos módulos.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("sample-app")

    # Evita adicionar handlers duplicados em reimportações
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Formatter JSON — campos fixos + extras injetados pelo OtelTraceFilter
    json_fmt = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s %(span_id)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "service",
        },
    )

    otel_filter = OtelTraceFilter()

    # Handler 1 — arquivo (consumido pelo Filebeat → Logstash → OpenSearch)
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3
    )
    file_handler.setFormatter(json_fmt)
    file_handler.setLevel(logging.DEBUG)
    file_handler.addFilter(otel_filter)

    # Handler 2 — stdout (visível no `docker logs`, também em JSON)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(json_fmt)
    console_handler.setLevel(logging.INFO)
    console_handler.addFilter(otel_filter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger
