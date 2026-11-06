"""
Contrato: TaskDispatcher

Define como despachar tarefas assíncronas em background.
O Use Case depende desta abstração — nunca de asyncio.create_task ou Celery diretamente.

Implementação Fase 1: infrastructure/background/asyncio_task_dispatcher.py
Implementação Fase 2: infrastructure/background/celery_task_dispatcher.py

Trocar a implementação não requer alterar nenhum Use Case — apenas o
registro em presentation/api/dependencies.py.
"""

from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import Any


class TaskDispatcher(ABC):
    @abstractmethod
    def dispatch(self, coro: Coroutine[Any, Any, None]) -> None:
        """
        Despacha uma coroutine para execução em background, sem aguardar o resultado.

        Args:
            coro: Coroutine a ser executada de forma assíncrona
                  (ex: o pipeline completo do Use Case IngestRepository).
        """
        ...

