# =============================================================================
# sample-app — Instrumentação OpenTelemetry (Traces)
# Card 6 : Sem traces (stub vazio)
# Card 8 : Descomentar e implementar TracerProvider + OTLP exporter
# =============================================================================

# ── Card 8 — Descomentar tudo abaixo ──────────────────────────────────────────
#
# from opentelemetry import trace
# from opentelemetry.sdk.trace import TracerProvider
# from opentelemetry.sdk.trace.export import BatchSpanProcessor
# from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
# from opentelemetry.sdk.resources import Resource, SERVICE_NAME
# from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
#
# from app.config import APP_NAME, OTEL_EXPORTER_ENDPOINT
#
#
# def setup_tracing(app) -> None:
#     """Configura o TracerProvider e instrumenta o FastAPI automaticamente."""
#     resource = Resource.create({SERVICE_NAME: APP_NAME})
#     provider = TracerProvider(resource=resource)
#     exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_ENDPOINT, insecure=True)
#     provider.add_span_processor(BatchSpanProcessor(exporter))
#     trace.set_tracer_provider(provider)
#
#     # Auto-instrumentação: captura todos os endpoints automaticamente
#     FastAPIInstrumentor.instrument_app(app)
#
#
# def get_tracer() -> trace.Tracer:
#     return trace.get_tracer(APP_NAME)
