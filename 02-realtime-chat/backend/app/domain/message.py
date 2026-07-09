from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Message:
    id: int
    room: str
    username: str
    content: str
    created_at: datetime
