import unittest

from fastapi import FastAPI
from opentelemetry import context, trace

from app.telemetry import (
    extract_context_from_payload,
    get_tracer,
    inject_context_into_payload,
    setup_tracing,
)


class TelemetrySetupTests(unittest.TestCase):
    def test_setup_tracing_registers_global_tracer(self) -> None:
        app = FastAPI()

        setup_tracing(app)

        self.assertIsNotNone(get_tracer())

    def test_trace_context_round_trips_through_redis_payload(self) -> None:
        tracer = get_tracer()

        with tracer.start_as_current_span("root-span") as span:
            payload = {"room": "general", "username": "Alice", "content": "hello"}
            payload_with_context = inject_context_into_payload(payload)
            extracted = extract_context_from_payload(payload_with_context)
            token = context.attach(extracted)
            try:
                current = trace.get_current_span(extracted)
                self.assertEqual(
                    current.get_span_context().trace_id,
                    span.get_span_context().trace_id,
                )
            finally:
                context.detach(token)


if __name__ == "__main__":
    unittest.main()
