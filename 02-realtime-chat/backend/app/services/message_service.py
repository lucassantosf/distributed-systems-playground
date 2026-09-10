from app.domain.message import Message
from app.repositories.message_repository import MessageRepository
from app.telemetry import get_tracer


class MessageService:
    def __init__(self, repository: MessageRepository | None = None) -> None:
        self.repository = repository or MessageRepository()
        self.tracer = get_tracer()

    async def persist_message(self, *, room: str, username: str, content: str) -> Message:
        with self.tracer.start_as_current_span("chat.persist_message") as span:
            span.set_attribute("chat.room", room)
            span.set_attribute("chat.username", username)
            span.set_attribute("chat.message_length", len(content))
            return await self.repository.create_message(room=room, username=username, content=content)

    async def get_history(self, *, room: str) -> list[Message]:
        with self.tracer.start_as_current_span("chat.get_history") as span:
            span.set_attribute("chat.room", room)
            return await self.repository.list_messages_by_room(room)
