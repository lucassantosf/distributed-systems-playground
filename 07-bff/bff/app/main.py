import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.exceptions import BFFException, bff_exception_handler
from app.routers import orders, users

app = FastAPI(title="BFF", version="0.1.0")

# Register custom exception handler for BFFException
app.add_exception_handler(BFFException, bff_exception_handler)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Standardizes unexpected or built-in HTTPExceptions into the unified BFF error format."""
    type_map = {
        404: "not_found",
        504: "timeout",
        503: "service_unavailable",
        422: "validation_error",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": str(exc.detail),
            "service": "bff",
            "type": type_map.get(exc.status_code, "http_error"),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catches all unhandled exceptions to prevent internal implementation leaks."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "An unexpected internal server error occurred",
            "service": "bff",
            "type": "internal_error",
        },
    )


app.include_router(orders.router)
app.include_router(users.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "bff"}


@app.get("/health/downstream")
async def health_downstream():
    """Verifica a conectividade do BFF com cada serviço downstream."""
    services = {
        "user-service": f"{settings.user_service_url}/health",
        "product-service": f"{settings.product_service_url}/health",
        "order-service": f"{settings.order_service_url}/health",
    }

    results = {}
    async with httpx.AsyncClient(timeout=settings.downstream_timeout) as client:
        for name, url in services.items():
            try:
                response = await client.get(url)
                results[name] = {"status": "ok", "http_status": response.status_code}
            except httpx.TimeoutException:
                results[name] = {"status": "error", "detail": "timeout"}
            except Exception as e:
                results[name] = {"status": "error", "detail": str(e)}

    all_ok = all(r["status"] == "ok" for r in results.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "downstream": results,
    }
