"""
CeleryTaskDispatcher — Card F2-1

Implementação concreta de TaskDispatcher que enfileira tarefas assíncronas
no Celery usando Redis como message broker.
"""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

from src.application.interfaces.task_dispatcher import TaskDispatcher
from src.infrastructure.background.celery_tasks import ingest_repository_task

logger = logging.getLogger(__name__)


class CeleryTaskDispatcher(TaskDispatcher):
    """
    Despacha a tarefa de ingestão para o worker Celery via Redis.
    Implementa o contrato TaskDispatcher sem que nenhuma rota ou Use Case precise mudar.
    """

    def dispatch(self, coro: Coroutine[Any, Any, None]) -> None:
        """
        Extrai os parâmetros do DTO contidos no frame da coroutine criada pelo Use Case
        e dispara a task Celery correspondente via .delay().
        """
        dto = coro.cr_frame.f_locals.get("dto") if coro.cr_frame else None

        if dto and hasattr(dto, "repo_id") and hasattr(dto, "github_url"):
            coro.close()  # Fecha a coroutine para evitar RuntimeWarning
            task = ingest_repository_task.delay(str(dto.repo_id), dto.github_url)
            logger.info(
                "Tarefa de ingestão despachada para o Celery (task_id=%s, repo_id=%s)",
                task.id,
                dto.repo_id,
            )
        else:
            # Fallback gracioso caso seja outra coroutine
            logger.warning(
                "Não foi possível extrair DTO da coroutine. Executando via asyncio.create_task como fallback."
            )
            asyncio.create_task(coro)
