import json
import os

import redis.asyncio as redis

class RedisPublisher:
    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://redis:6379")
        self.client = redis.from_url(self.redis_url, decode_responses=True)

    async def publish_message(self, room: str, payload: dict) -> None:
        channel = f"chat:{room}"
        await self.client.publish(channel, json.dumps(payload))
