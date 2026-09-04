# =============================================================================
# producer-api — Instrumentação OpenTelemetry (Traces)
# Card 18.1: TracerProvider + OTLP exporter + span root manual por request
#
# Nota: não usamos FastAPIInstrumentor pois opentelemetry-instrumentation
# depende de pkg_resources (setuptools) que não está disponível no
# python:3.12-slim. Em vez disso, criamos um middleware ASGI que gera o
# span raiz para cada requisição HTTP de forma equivalente.
# =============================================================================
import os
import time

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry import propagate

_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "producer-api")
_OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
_OTEL_ENV = os.getenv("OTEL_ENV", "local")

_propagator = CompositePropagator([TraceContextTextMapPropagator()])


def setup_tracing(app) -> None:
    """
    Configura o TracerProvider global e adiciona um middleware ASGI que cria
    um span raiz para cada requisição HTTP, equivalente ao FastAPIInstrumentor
    mas sem a dependência de pkg_resources.
    """
    resource = Resource.create({
        "service.name": _SERVICE_NAME,
        "service.version": "1.0.0",
        "deployment.environment": _OTEL_ENV,
    })

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=_OTEL_ENDPOINT,
        insecure=True,
    )
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    propagate.set_global_textmap(_propagator)

    tracer = trace.get_tracer(_SERVICE_NAME)

    # Middleware ASGI: cria span raiz para cada requisição
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request

    class TracingMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Extrai contexto de propagação W3C (traceparent/tracestate)
            ctx = propagate.extract(dict(request.headers))
            method = request.method
            route = request.url.path

            with tracer.start_as_current_span(
                f"{method} {route}",
                context=ctx,
                kind=trace.SpanKind.SERVER,
            ) as span:
                span.set_attribute("http.method", method)
                span.set_attribute("http.route", route)
                span.set_attribute("http.url", str(request.url))
                span.set_attribute("http.host", request.headers.get("host", ""))

                start = time.time()
                response = await call_next(request)
                duration_ms = round((time.time() - start) * 1000, 2)

                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("http.duration_ms", duration_ms)

                if response.status_code >= 500:
                    span.set_status(trace.StatusCode.ERROR)

                return response

    app.add_middleware(TracingMiddleware)


def get_tracer() -> trace.Tracer:
    """Retorna o tracer global para criar spans filhos manualmente."""
    return trace.get_tracer(_SERVICE_NAME)
