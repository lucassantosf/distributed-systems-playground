import asyncio
import json
import logging
import time
from typing import Dict

from fastapi import WebSocket

logger = logging.getLogger("chat")

PING_INTERVAL = 30
PONG_TIMEOUT = 60


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: Dict[str, Dict[str, WebSocket]] = {}
        self._last_pong: Dict[str, Dict[str, float]] = {}
        self._lock = asyncio.Lock()

    async def add_connection(self, room: str, username: str, websocket: WebSocket) -> None:
        async with self._lock:
            room_connections = self._rooms.setdefault(room, {})
            room_connections[username] = websocket
            room_pong = self._last_pong.setdefault(room, {})
            room_pong[username] = time.time()

    async def remove_connection(self, room: str, username: str) -> None:
        async with self._lock:
            room_connections = self._rooms.get(room)
            if not room_connections:
                return

            room_connections.pop(username, None)
            if not room_connections:
                self._rooms.pop(room, None)

            room_pong = self._last_pong.get(room)
            if room_pong:
                room_pong.pop(username, None)
                if not room_pong:
                    self._last_pong.pop(room, None)

    async def update_pong(self, room: str, username: str) -> None:
        async with self._lock:
            room_pong = self._last_pong.get(room)
            if room_pong and username in room_pong:
                room_pong[username] = time.time()
        logger.info("[heartbeat] pong received from %s in room %s", username, room)

    async def get_room_users(self, room: str) -> list[str]:
        async with self._lock:
            room_connections = self._rooms.get(room, {})
            return sorted(room_connections.keys())

    async def get_all_rooms(self) -> Dict[str, list[str]]:
        async with self._lock:
            return {room: sorted(connections.keys()) for room, connections in self._rooms.items()}

    async def broadcast(self, room: str, sender_username: str, message: str, *, exclude_username: str | None = None) -> None:
        await self.broadcast_text(room, f"{sender_username}: {message}", exclude_username=exclude_username)

    async def broadcast_text(self, room: str, message: str, *, exclude_username: str | None = None) -> None:
        async with self._lock:
            room_connections = self._rooms.get(room, {})
            recipients = list(room_connections.items())

        for username, websocket in recipients:
            if exclude_username is not None and username == exclude_username:
                continue
            try:
                await websocket.send_text(message)
            except Exception:
                await self.remove_connection(room, username)

    async def start_heartbeat(self) -> None:
        while True:
            await asyncio.sleep(PING_INTERVAL)

            async with self._lock:
                connections = {room: dict(users) for room, users in self._rooms.items()}

            total_users = sum(len(users) for users in connections.values())
            if total_users > 0:
                logger.info("[heartbeat] sending ping to %d user(s)", total_users)

            for room, users in connections.items():
                for username, websocket in users.items():
                    try:
                        await websocket.send_text(json.dumps({"type": "ping"}))
                    except Exception:
                        await self.remove_connection(room, username)

            now = time.time()
            async with self._lock:
                stale = []
                for room, users in self._last_pong.items():
                    for username, last_pong in users.items():
                        if now - last_pong > PONG_TIMEOUT:
                            stale.append((room, username))

            for room, username in stale:
                logger.warning("Heartbeat timeout for %s in room %s", username, room)
                await self.remove_connection(room, username)
