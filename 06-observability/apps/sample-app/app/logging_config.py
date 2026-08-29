# =============================================================================
# sample-app — Configuração de logging
# Card 6 : Logging padrão Python → arquivo + console
# Card 9 : Substituído por JSON estruturado com trace_id/span_id
# =============================================================================
import logging
import logging.handlers
import os
import sys

from app.config import LOG_FILE, LOG_DIR


def setup_logging() -> logging.Logger:
    """
    Configura o logger da aplicação.
    Card 6 : formato texto legível, escrevendo em arquivo e console.
    Card 9 : este módulo será atualizado para emitir JSON com trace_id/span_id.

    Usa um guarda (hasHandlers) para evitar duplicação de handlers caso
    setup_logging() seja chamado em múltiplos módulos.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("sample-app")

    # Evita adicionar handlers duplicados em reimportações
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Formato: timestamp | level | message
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Handler 1 — arquivo (consumido pelo Filebeat)
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)

    # Handler 2 — stdout (visível no `docker logs`)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger
