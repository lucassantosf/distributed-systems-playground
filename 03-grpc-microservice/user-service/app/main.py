import time
import logging
import uuid as uuid_lib

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from database import engine
from routers.user import router as user_router
from interceptors.logging import setup_logging, set_request_id

setup_logging("user-service")

logger = logging.getLogger("http.user-service")

app = FastAPI(title="User Service")


class HTTPLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid_lib.uuid4())[:8])
        set_request_id(request_id)
        start = time.time()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed = round((time.time() - start) * 1000)
            logger.info(
                "%s %s | %dms | %d",
                request.method, request.url.path, elapsed, status_code,
                extra={
                    "request_id": request_id,
                    "method": f"HTTP {request.method} {request.url.path}",
                    "latency_ms": elapsed,
                    "status": str(status_code),
                },
            )


app.add_middleware(HTTPLoggingMiddleware)
app.include_router(user_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = {}
    for error in exc.errors():
        loc = error["loc"]
        if len(loc) > 1:
            field = loc[-1]
        else:
            field = loc[0]
        errors[field] = error["msg"]
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Invalid request data",
            "details": errors,
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=500,
        content={
            "error": "database_error",
            "message": "Database operation failed",
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
        },
    )


def check_database():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "healthy"
    except Exception:
        return "unhealthy"


@app.get("/health")
def health_check():
    checks = {"database": check_database()}
    status = "healthy" if checks["database"] == "healthy" else "unhealthy"
    return {"status": status, "service": "user-service", "checks": checks}
