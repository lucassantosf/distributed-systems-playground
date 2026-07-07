import asyncio
from typing import Dict, Set


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def add_connection(self, room: str, username: str) -> None:
        async with self._lock:
            users = self._rooms.setdefault(room, set())
            users.add(username)

    async def remove_connection(self, room: str, username: str) -> None:
        async with self._lock:
            users = self._rooms.get(room)
            if not users:
                return

            users.discard(username)
            if not users:
                self._rooms.pop(room, None)

    async def get_room_users(self, room: str) -> list[str]:
        async with self._lock:
            users = self._rooms.get(room, set())
            return sorted(users)

    async def get_all_rooms(self) -> Dict[str, list[str]]:
        async with self._lock:
            return {room: sorted(users) for room, users in self._rooms.items()}
