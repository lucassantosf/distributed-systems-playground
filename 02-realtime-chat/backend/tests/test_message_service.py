import unittest

from app.infrastructure.database import ensure_schema
from app.repositories.message_repository import MessageRepository
from app.services.message_service import MessageService


class MessageServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await ensure_schema()
        await MessageRepository().clear_all()

    async def asyncTearDown(self) -> None:
        await MessageRepository().clear_all()

    async def test_persists_message_for_room(self) -> None:
        service = MessageService(repository=MessageRepository())

        created = await service.persist_message(
            room="general",
            username="Alice",
            content="hello from the service",
        )

        self.assertEqual(created.room, "general")
        self.assertEqual(created.username, "Alice")

        messages = await MessageRepository().list_messages_by_room("general")
        self.assertEqual([message.content for message in messages], ["hello from the service"])


if __name__ == "__main__":
    unittest.main()
