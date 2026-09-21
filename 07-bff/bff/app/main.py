import httpx
from fastapi import FastAPI

from app.config import settings
from app.routers import orders

app = FastAPI(title="BFF", version="0.1.0")

app.include_router(orders.router)


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
