from app.domain.message import Message
from app.repositories.message_repository import MessageRepository


class MessageService:
    def __init__(self, repository: MessageRepository | None = None) -> None:
        self.repository = repository or MessageRepository()

    async def persist_message(self, *, room: str, username: str, content: str) -> Message:
        return await self.repository.create_message(room=room, username=username, content=content)
