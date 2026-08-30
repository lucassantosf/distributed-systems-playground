# =============================================================================
# sample-app — Instrumentação OpenTelemetry (Traces)
# Card 8 : TracerProvider + OTLP exporter para OTel Collector
# =============================================================================
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.config import APP_NAME, APP_ENV, OTEL_EXPORTER_ENDPOINT


def setup_tracing(app) -> None:
    """
    Configura o TracerProvider global e instrumenta o FastAPI automaticamente.

    O que isso faz:
    - Cria um Resource identificando o serviço (service.name = APP_NAME)
    - Configura o OTLP exporter apontando para o OTel Collector via gRPC
    - Usa BatchSpanProcessor para envio eficiente (não bloqueante)
    - FastAPIInstrumentor captura automaticamente todos os endpoints como spans raiz
    """
    resource = Resource.create({
        SERVICE_NAME: APP_NAME,
        "service.version": "1.0.0",
        "deployment.environment": APP_ENV,
    })

    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint=OTEL_EXPORTER_ENDPOINT,
        insecure=True,  # sem TLS em ambiente de dev
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))

    # Registra como provider global — trace.get_tracer() usa este provider
    trace.set_tracer_provider(provider)

    # Auto-instrumentação: todo endpoint FastAPI vira um span raiz automaticamente
    # com atributos http.method, http.route, http.status_code, etc.
    FastAPIInstrumentor.instrument_app(app)


def get_tracer() -> trace.Tracer:
    """Retorna o tracer global para criar spans filhos manualmente."""
    return trace.get_tracer(APP_NAME)
