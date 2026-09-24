import json
import logging
from typing import Any
from redis.asyncio import Redis, RedisError

from app.config import settings

logger = logging.getLogger("bff.cache")

redis_client: Redis | None = None


def get_redis_client() -> Redis:
    global redis_client
    if redis_client is None:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return redis_client


async def close_redis() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None


async def ping_redis() -> bool:
    try:
        client = get_redis_client()
        return await client.ping()
    except Exception as e:
        logger.warning(f"Redis ping failed: {e}")
        return False


async def get_cache(key: str) -> Any | None:
    try:
        client = get_redis_client()
        data = await client.get(key)
        if data is not None:
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Error reading from Redis key '{key}': {e}")
    return None


async def set_cache(key: str, value: Any, ttl: int | None = None) -> bool:
    if ttl is None:
        ttl = settings.cache_ttl
    try:
        client = get_redis_client()
        serialized = json.dumps(value)
        await client.set(key, serialized, ex=ttl)
        return True
    except Exception as e:
        logger.warning(f"Error writing to Redis key '{key}': {e}")
        return False


async def delete_cache(key: str) -> bool:
    try:
        client = get_redis_client()
        await client.delete(key)
        return True
    except Exception as e:
        logger.warning(f"Error deleting Redis key '{key}': {e}")
        return False

