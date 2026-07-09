from datetime import datetime

from app.domain.message import Message
from app.infrastructure.database import get_db_connection


class MessageRepository:
    async def create_message(self, *, room: str, username: str, content: str) -> Message:
        conn = await get_db_connection()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO messages (room, username, content, created_at)
                VALUES ($1, $2, $3, $4)
                RETURNING id, room, username, content, created_at
                """,
                room,
                username,
                content,
                datetime.now(),
            )
            return Message(
                id=row["id"],
                room=row["room"],
                username=row["username"],
                content=row["content"],
                created_at=row["created_at"],
            )
        finally:
            await conn.close()

    async def list_messages_by_room(self, room: str) -> list[Message]:
        conn = await get_db_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT id, room, username, content, created_at
                FROM messages
                WHERE room = $1
                ORDER BY created_at ASC, id ASC
                """,
                room,
            )
            return [
                Message(
                    id=row["id"],
                    room=row["room"],
                    username=row["username"],
                    content=row["content"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
        finally:
            await conn.close()

    async def clear_all(self) -> None:
        conn = await get_db_connection()
        try:
            await conn.execute("DELETE FROM messages")
        finally:
            await conn.close()
