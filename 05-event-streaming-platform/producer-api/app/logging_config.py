# =============================================================================
# producer-api — Configuração de Logging Estruturado JSON
# Card 18.2: logging JSON com trace_id/span_id injetados do OTel
# =============================================================================
import logging
import logging.handlers
import os
import sys

from opentelemetry import trace

_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "producer-api")
_LOG_DIR = "/app/logs"
_LOG_FILE = os.path.join(_LOG_DIR, "producer-api.log")


class OtelTraceFilter(logging.Filter):
    """
    Injeta trace_id e span_id do span OTel ativo em cada log record.
    Quando dentro de um span ativo (ex: request HTTP), os IDs são extraídos
    e adicionados ao log — permitindo correlação Log → Trace no Grafana.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        span = trace.get_current_span()
        ctx = span.get_span_context()

        if ctx.is_valid:
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        else:
            record.trace_id = ""
            record.span_id = ""

        return True


class JsonFormatter(logging.Formatter):
    """Formatter JSON simples sem dependência de python-json-logger."""

    import json as _json

    def format(self, record: logging.LogRecord) -> str:
        import json
        self.format_exception_if_needed(record)
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "service": _SERVICE_NAME,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", ""),
            "span_id": getattr(record, "span_id", ""),
            "logger": record.name,
        }
        return json.dumps(payload, ensure_ascii=False)

    def format_exception_if_needed(self, record: logging.LogRecord) -> None:
        if record.exc_info:
            record.exc_text = self.formatException(record.exc_info)


def setup_logging() -> logging.Logger:
    """
    Configura o logger do producer-api em modo JSON estruturado.

    Cada linha de log é um objeto JSON com os campos:
      timestamp, level, service, message, trace_id, span_id

    - Arquivo: /app/logs/producer-api.log (coletado pelo Filebeat)
    - Console: stdout (visível no docker logs)
    """
    os.makedirs(_LOG_DIR, exist_ok=True)

    logger = logging.getLogger(_SERVICE_NAME)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    json_fmt = JsonFormatter()
    otel_filter = OtelTraceFilter()

    # Handler 1 — arquivo (consumido pelo Filebeat → Logstash → OpenSearch)
    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3
    )
    file_handler.setFormatter(json_fmt)
    file_handler.setLevel(logging.DEBUG)
    file_handler.addFilter(otel_filter)

    # Handler 2 — stdout (visível no docker compose logs, também em JSON)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(json_fmt)
    console_handler.setLevel(logging.INFO)
    console_handler.addFilter(otel_filter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger
