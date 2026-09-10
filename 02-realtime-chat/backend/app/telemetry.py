import os
from typing import Any

from opentelemetry import context, propagate, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

APP_NAME = os.getenv("OTEL_SERVICE_NAME", "chat-backend")
APP_ENV = os.getenv("APP_ENV", "development")
OTEL_EXPORTER_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")


def setup_tracing(app) -> None:
    """Configure the global tracer provider and instrument the FastAPI app."""
    if not getattr(app.state, "otel_instrumented", False):
        resource = Resource.create(
            {
                SERVICE_NAME: APP_NAME,
                "service.version": "1.0.0",
                "deployment.environment": APP_ENV,
                "service.namespace": "distributed-systems-playground",
            }
        )

        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_ENDPOINT, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        if not isinstance(trace.get_tracer_provider(), TracerProvider):
            trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        app.state.otel_instrumented = True


def get_tracer():
    return trace.get_tracer(APP_NAME)


def inject_context_into_payload(payload: dict[str, Any]) -> dict[str, Any]:
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    enriched = dict(payload)
    if carrier.get("traceparent"):
        enriched["traceparent"] = carrier["traceparent"]
    if carrier.get("tracestate"):
        enriched["tracestate"] = carrier["tracestate"]
    return enriched


def extract_context_from_payload(payload: dict[str, Any]):
    carrier = {}
    for key in ("traceparent", "tracestate"):
        value = payload.get(key)
        if value:
            carrier[key] = value
    return propagate.extract(carrier) if carrier else context.get_current()
