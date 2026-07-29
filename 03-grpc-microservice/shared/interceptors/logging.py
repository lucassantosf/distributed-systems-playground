import os
import json
import time
import uuid
import random
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

import grpc

LOG_DIR = "/logs"

_file_handler_added = False

_current_request_id: ContextVar[str] = ContextVar("current_request_id", default=None)


def set_request_id(request_id: str):
    _current_request_id.set(request_id)


def get_request_id() -> str:
    return _current_request_id.get()


class ResilientFileHandler(logging.FileHandler):
    def __init__(self, filename, **kwargs):
        self._filename = filename
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        super().__init__(filename, **kwargs)

    def emit(self, record):
        try:
            if self.stream is None or self.stream.closed:
                self.stream = self._open()
            elif not os.path.exists(self._filename):
                self.stream.close()
                os.makedirs(os.path.dirname(self._filename), exist_ok=True)
                self.stream = self._open()
        except Exception:
            pass
        super().emit(record)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "service": getattr(record, "service", "unknown"),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for key in ["request_id", "method", "latency_ms", "status", "caller", "error"]:
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, ensure_ascii=False)


class ServiceContextFilter(logging.Filter):
    def __init__(self, service_name):
        self.service_name = service_name

    def filter(self, record):
        record.service = self.service_name
        return True


def setup_logging(service_name: str):
    global _file_handler_added
    if _file_handler_added:
        return

    log_file = os.path.join(LOG_DIR, f"{service_name}.log")
    os.makedirs(LOG_DIR, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    context_filter = ServiceContextFilter(service_name)
    formatter = JsonFormatter()

    file_handler = ResilientFileHandler(log_file)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)
    root_logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(context_filter)
    root_logger.addHandler(stream_handler)

    _file_handler_added = True


def _extract_metadata(context):
    metadata = {}
    if context and hasattr(context, "invocation_metadata"):
        for key, value in context.invocation_metadata():
            metadata[key] = value
    return metadata


class LoggingServerInterceptor(grpc.ServerInterceptor):
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = logging.getLogger(f"grpc.{service_name}")

    def intercept_service(self, continuation, handler_call_details):
        method = handler_call_details.method
        method_name = method.lstrip("/")

        handler = continuation(handler_call_details)
        if handler is None:
            return handler

        if handler.unary_unary:
            return grpc.unary_unary_rpc_method_handler(
                self._wrap_unary(handler.unary_unary, method_name),
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
        return handler

    def _wrap_unary(self, behavior, method_name):
        def wrapper(request, context):
            meta = _extract_metadata(context)
            request_id = meta.get("x-request-id", str(uuid.uuid4())[:8])
            caller = meta.get("x-forwarded-for", "-")

            start = time.time()
            status = "OK"
            try:
                return behavior(request, context)
            except Exception:
                status = "ERROR"
                raise
            finally:
                elapsed = round((time.time() - start) * 1000)
                self.logger.info(
                    "%s | %dms | %s",
                    method_name, elapsed, status,
                    extra={
                        "request_id": request_id,
                        "method": method_name,
                        "latency_ms": elapsed,
                        "status": status,
                        "caller": caller,
                    },
                )
        return wrapper


class LoggingClientInterceptor(grpc.UnaryUnaryClientInterceptor):
    def __init__(self, service_name: str, metadata_name: str = None):
        self.service_name = service_name
        self.metadata_name = metadata_name or service_name
        self.logger = logging.getLogger(f"grpc.{service_name}")

    def intercept_unary_unary(self, continuation, client_call_details, request):
        method = client_call_details.method
        method_name = method.lstrip("/")

        existing_metadata = dict(client_call_details.metadata) if client_call_details.metadata else {}
        request_id = existing_metadata.get("x-request-id") or get_request_id() or str(uuid.uuid4())[:8]
        timestamp = datetime.now(timezone.utc).isoformat()

        existing_metadata["x-request-id"] = request_id
        existing_metadata["x-forwarded-for"] = self.metadata_name
        existing_metadata["x-timestamp"] = timestamp

        new_details = _ClientCallDetails(
            method=client_call_details.method,
            timeout=client_call_details.timeout,
            credentials=client_call_details.credentials,
            metadata=tuple(existing_metadata.items()),
            compression=client_call_details.compression,
        )

        start = time.time()
        try:
            response = continuation(new_details, request)
            elapsed = round((time.time() - start) * 1000)
            self.logger.info(
                "%s | %dms | OK",
                method_name, elapsed,
                extra={
                    "request_id": request_id,
                    "method": method_name,
                    "latency_ms": elapsed,
                    "status": "OK",
                },
            )
            return response
        except grpc.RpcError as e:
            elapsed = round((time.time() - start) * 1000)
            self.logger.info(
                "%s | %dms | %s",
                method_name, elapsed, e.code().name,
                extra={
                    "request_id": request_id,
                    "method": method_name,
                    "latency_ms": elapsed,
                    "status": e.code().name,
                    "error": str(e.details()),
                },
            )
            raise


class _ClientCallDetails(grpc.ClientCallDetails):
    def __init__(self, method, timeout, credentials, metadata, compression):
        self.method = method
        self.timeout = timeout
        self.credentials = credentials
        self.metadata = metadata
        self.compression = compression


RETRYABLE_CODES = {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED}


class RetryClientInterceptor(grpc.UnaryUnaryClientInterceptor):
    def __init__(self, service_name: str, max_retries: int = 3, base_delay: float = 0.5):
        self.service_name = service_name
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.logger = logging.getLogger(f"retry.{service_name}")

    def intercept_unary_unary(self, continuation, client_call_details, request):
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                call_future = continuation(client_call_details, request)
                response = call_future.result()
                return call_future
            except grpc.RpcError as e:
                last_error = e
                if e.code() not in RETRYABLE_CODES or attempt == self.max_retries:
                    raise
                delay = self._backoff(attempt)
                request_id = get_request_id() or "-"
                self.logger.info(
                    "Retry %d/%d for %s after %.1fs | %s",
                    attempt + 1, self.max_retries,
                    client_call_details.method.lstrip("/"),
                    delay, e.code().name,
                    extra={
                        "request_id": request_id,
                        "method": client_call_details.method.lstrip("/"),
                        "status": e.code().name,
                        "retry": attempt + 1,
                        "max_retries": self.max_retries,
                        "delay_ms": round(delay * 1000),
                        "error": str(e.details()),
                    },
                )
                time.sleep(delay)
            except Exception as e:
                last_error = e
                if attempt == self.max_retries:
                    raise
                time.sleep(self._backoff(attempt))
        raise last_error

    def _backoff(self, attempt: int) -> float:
        delay = min(self.base_delay * (2 ** attempt), 5.0)
        jitter = random.uniform(0, 0.5 * delay)
        return delay + jitter
