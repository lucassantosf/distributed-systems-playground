import unittest

from app.database import ensure_schema
from app.message_repository import MessageRepository


class MessageRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await ensure_schema()
        await MessageRepository().clear_all()

    async def asyncTearDown(self) -> None:
        await MessageRepository().clear_all()

    async def test_create_and_list_messages_by_room(self) -> None:
        repository = MessageRepository()

        created = await repository.create_message(
            room="general",
            username="Alice",
            content="Hello from the test",
        )

        self.assertEqual(created.room, "general")
        self.assertEqual(created.username, "Alice")
        self.assertEqual(created.content, "Hello from the test")

        general_messages = await repository.list_messages_by_room("general")
        python_messages = await repository.list_messages_by_room("python")

        self.assertEqual(len(general_messages), 1)
        self.assertEqual(general_messages[0].content, "Hello from the test")
        self.assertEqual(len(python_messages), 0)


if __name__ == "__main__":
    unittest.main()
