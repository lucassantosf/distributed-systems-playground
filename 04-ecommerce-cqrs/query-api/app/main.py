from fastapi import FastAPI
import redis

from config import settings

app = FastAPI(title="Query API")

redis_client = redis.from_url(settings.redis_url)


@app.get("/health")
async def health():
    redis_ok = False
    try:
        redis_client.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return {"status": "ok" if redis_ok else "degraded", "redis": "healthy" if redis_ok else "unhealthy"}
