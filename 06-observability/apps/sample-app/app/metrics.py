# =============================================================================
# sample-app — Métricas Prometheus
# Card 7 : Contadores e histograma para instrumentar os endpoints HTTP
# =============================================================================
from prometheus_client import Counter, Histogram, make_asgi_app

# Contador de requisições por método, rota e status HTTP
http_requests_total = Counter(
    "http_requests_total",
    "Total de requisições HTTP recebidas",
    labelnames=["method", "endpoint", "status"],
)

# Histograma de latência por método e rota
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Duração das requisições HTTP em segundos",
    labelnames=["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
)

# Contador de pedidos criados com sucesso
app_orders_created_total = Counter(
    "app_orders_created_total",
    "Total de pedidos criados com sucesso",
)


def get_metrics_app():
    """Retorna a ASGI app do /metrics para montar no FastAPI."""
    return make_asgi_app()
