"""
Configuração do Celery — Fase 2 (Card F2-1)

Inicializa e configura a aplicação Celery usando Redis como message broker
e result backend.
"""

from celery import Celery

from src.settings import settings

celery_app = Celery(
    "ai_engineering_assistant",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.infrastructure.background.celery_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)
