import asyncio
from collections.abc import Coroutine
from typing import Any

from src.application.interfaces.task_dispatcher import TaskDispatcher


class AsyncioTaskDispatcher(TaskDispatcher):
    def dispatch(self, coro: Coroutine[Any, Any, None]) -> None:
        asyncio.create_task(coro)

