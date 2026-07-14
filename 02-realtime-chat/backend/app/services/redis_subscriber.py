import asyncio
import json
import os

import redis.asyncio as redis

from app.services.connection_manager import ConnectionManager


class RedisSubscriber:
    def __init__(self, connection_manager: ConnectionManager, redis_url: str | None = None) -> None:
        self.connection_manager = connection_manager
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://redis:6379")
        self.client = redis.from_url(self.redis_url, decode_responses=True)
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None:
            return

        self._task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _listen(self) -> None:
        pubsub = self.client.pubsub()
        await pubsub.psubscribe("chat:*")
        try:
            async for message in pubsub.listen():
                if message.get("type") != "pmessage":
                    continue

                channel = message.get("channel", "")
                payload = message.get("data", "")
                if not channel or not payload:
                    continue

                try:
                    envelope = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                room = envelope.get("room")
                if not room:
                    continue

                await self.connection_manager.broadcast(
                    room,
                    envelope.get("username", "System"),
                    envelope.get("content", ""),
                    exclude_username=envelope.get("username"),
                )
        finally:
            await pubsub.close()
