import asyncio
from typing import Dict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: Dict[str, Dict[str, WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def add_connection(self, room: str, username: str, websocket: WebSocket) -> None:
        async with self._lock:
            room_connections = self._rooms.setdefault(room, {})
            room_connections[username] = websocket

    async def remove_connection(self, room: str, username: str) -> None:
        async with self._lock:
            room_connections = self._rooms.get(room)
            if not room_connections:
                return

            room_connections.pop(username, None)
            if not room_connections:
                self._rooms.pop(room, None)

    async def get_room_users(self, room: str) -> list[str]:
        async with self._lock:
            room_connections = self._rooms.get(room, {})
            return sorted(room_connections.keys())

    async def get_all_rooms(self) -> Dict[str, list[str]]:
        async with self._lock:
            return {room: sorted(connections.keys()) for room, connections in self._rooms.items()}

    async def broadcast(self, room: str, sender_username: str, message: str) -> None:
        async with self._lock:
            room_connections = self._rooms.get(room, {})
            recipients = list(room_connections.items())

        for username, websocket in recipients:
            try:
                await websocket.send_text(f"{sender_username}: {message}")
            except Exception:
                await self.remove_connection(room, username)
