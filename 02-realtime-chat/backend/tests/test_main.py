import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import WebSocketDisconnect

from app.main import websocket_endpoint


class DummyWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent_messages: list[str] = []
        self._messages = ["hello from the test"]
        self._calls = 0

    async def accept(self) -> None:
        self.accepted = True

    async def receive_text(self) -> str:
        self._calls += 1
        if self._calls == 1:
            return self._messages[0]
        raise WebSocketDisconnect()

    async def send_text(self, data: str) -> None:
        self.sent_messages.append(data)


class WebsocketFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_websocket_persists_and_publishes_without_local_broadcast(self) -> None:
        websocket = DummyWebSocket()
        manager = MagicMock()
        manager.add_connection = AsyncMock()
        manager.remove_connection = AsyncMock()
        manager.get_room_users = AsyncMock(return_value=["Alice"])
        manager.broadcast = AsyncMock()
        manager.broadcast_text = AsyncMock()

        message_service = MagicMock()
        message_service.persist_message = AsyncMock(return_value=SimpleNamespace(id=42))

        redis_publisher = MagicMock()
        redis_publisher.publish_message = AsyncMock()

        with (
            patch("app.main.manager", manager),
            patch("app.main.message_service", message_service),
            patch("app.main.redis_publisher", redis_publisher),
        ):
            await websocket_endpoint(websocket, room="general", username="Alice")

        manager.add_connection.assert_awaited_once_with("general", "Alice", websocket)
        message_service.persist_message.assert_awaited_once_with(room="general", username="Alice", content="hello from the test")
        redis_publisher.publish_message.assert_awaited_once()
        manager.broadcast.assert_not_called()
        manager.broadcast_text.assert_any_await("general", "System: Alice joined")
        manager.broadcast_text.assert_any_await("general", "System: Alice left")

    async def test_join_updates_presence_for_new_and_existing_users(self) -> None:
        websocket = DummyWebSocket()
        manager = MagicMock()
        manager.add_connection = AsyncMock()
        manager.remove_connection = AsyncMock()
        manager.get_room_users = AsyncMock(return_value=["Alice", "Bob"])
        manager.broadcast = AsyncMock()
        manager.broadcast_text = AsyncMock()

        message_service = MagicMock()
        message_service.persist_message = AsyncMock(return_value=SimpleNamespace(id=42))

        redis_publisher = MagicMock()
        redis_publisher.publish_message = AsyncMock()

        with (
            patch("app.main.manager", manager),
            patch("app.main.message_service", message_service),
            patch("app.main.redis_publisher", redis_publisher),
        ):
            await websocket_endpoint(websocket, room="general", username="Bob")

        self.assertIn("Active users: Alice, Bob", websocket.sent_messages)
        manager.broadcast_text.assert_any_await("general", "System: Bob joined")
        manager.broadcast_text.assert_any_await("general", "System: Bob left")

    async def test_disconnect_broadcasts_updated_user_list(self) -> None:
        websocket = DummyWebSocket()
        manager = MagicMock()
        manager.add_connection = AsyncMock()
        manager.remove_connection = AsyncMock()
        manager.get_room_users = AsyncMock(return_value=["Alice"])
        manager.broadcast = AsyncMock()
        manager.broadcast_text = AsyncMock()

        message_service = MagicMock()
        message_service.persist_message = AsyncMock(return_value=SimpleNamespace(id=42))

        redis_publisher = MagicMock()
        redis_publisher.publish_message = AsyncMock()

        with (
            patch("app.main.manager", manager),
            patch("app.main.message_service", message_service),
            patch("app.main.redis_publisher", redis_publisher),
        ):
            await websocket_endpoint(websocket, room="general", username="Alice")

        manager.remove_connection.assert_awaited_once_with("general", "Alice")
        manager.broadcast_text.assert_any_await("general", "Active users: Alice")
        manager.broadcast_text.assert_any_await("general", "System: Alice left")


if __name__ == "__main__":
    unittest.main()
