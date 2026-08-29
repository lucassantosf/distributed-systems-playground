# =============================================================================
# sample-app — Configuração da aplicação via variáveis de ambiente
# =============================================================================
import os

# Identificação da aplicação (usada nos logs e traces)
APP_NAME: str = os.getenv("APP_NAME", "sample-app")
APP_ENV: str = os.getenv("APP_ENV", "development")

# Diretório de logs compartilhado com Filebeat
LOG_DIR: str = os.getenv("LOG_DIR", "/logs")
LOG_FILE: str = f"{LOG_DIR}/{APP_NAME}.log"

# Card 8 — OTel Collector endpoint (descomentado no Card 8)
# OTEL_EXPORTER_ENDPOINT: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
