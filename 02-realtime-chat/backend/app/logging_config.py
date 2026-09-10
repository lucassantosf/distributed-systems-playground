import json
import logging
import logging.handlers
import os
import sys
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace


SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "chat-backend")
APP_ENV = os.getenv("APP_ENV", "development")
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE = os.path.join(LOG_DIR, "chat-backend.log")


class TraceContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        current_span = trace.get_current_span()
        span_context = current_span.get_span_context()
        record.trace_id = format(span_context.trace_id, "032x") if span_context and span_context.is_valid else ""
        record.span_id = format(span_context.span_id, "016x") if span_context and span_context.is_valid else ""
        return True


class JsonFormatter(logging.Formatter):
    _standard_fields = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "environment": APP_ENV,
            "event": getattr(record, "event", "application_log"),
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", ""),
            "span_id": getattr(record, "span_id", ""),
        }
        payload.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in self._standard_fields
                and key not in payload
                and not key.startswith("_")
            }
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging() -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("chat")

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = JsonFormatter()
    trace_filter = TraceContextFilter()

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(trace_filter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(trace_filter)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False
    return logger