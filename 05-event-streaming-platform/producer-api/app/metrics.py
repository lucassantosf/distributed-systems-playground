# =============================================================================
# producer-api — Métricas Prometheus
# Card 18.3: Contadores e histogramas para instrumentar HTTP e publicação Kafka
# =============================================================================
from prometheus_client import Counter, Histogram, make_asgi_app

# ---------------------------------------------------------------------------
# Métricas HTTP (análogas à sample-app)
# ---------------------------------------------------------------------------
http_requests_total = Counter(
    "http_requests_total",
    "Total de requisições HTTP recebidas pelo producer-api",
    labelnames=["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Duração das requisições HTTP em segundos",
    labelnames=["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
)

# ---------------------------------------------------------------------------
# Métricas específicas do Kafka (publicação de eventos)
# ---------------------------------------------------------------------------
kafka_events_published_total = Counter(
    "kafka_events_published_total",
    "Total de eventos publicados no Kafka pelo producer-api",
    labelnames=["topic", "status"],  # status: success | error
)

kafka_publish_duration_seconds = Histogram(
    "kafka_publish_duration_seconds",
    "Duração da publicação de eventos no Kafka em segundos",
    labelnames=["topic"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1],
)

# ---------------------------------------------------------------------------
# Contador de pedidos criados com sucesso
# ---------------------------------------------------------------------------
orders_created_total = Counter(
    "orders_created_total",
    "Total de pedidos criados com sucesso pelo producer-api",
)


def get_metrics_app():
    """Retorna a ASGI app do /metrics para montar no FastAPI."""
    return make_asgi_app()
