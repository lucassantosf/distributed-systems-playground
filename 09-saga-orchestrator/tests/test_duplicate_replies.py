"""
Testes de Proteção contra Replies Duplicadas — Card 6.3.

Valida que:
  - handle_reply busca a Saga e faz lock no SagaStep (SELECT FOR UPDATE)
  - Quando uma reply duplicada para um step já em status terminal chega:
      * O processamento é interrompido
      * O log 'duplicate reply ignored' é emitido
      * Nenhum comando subsequente é publicado
      * O estado da Saga permanece consistente
  - O RepliesConsumer faz ACK normalmente em caso de reply duplicada
  - Cobre tanto o fluxo normal (COMPLETED) quanto compensação (COMPENSATED / COMPENSATING_FAILED)
"""
import asyncio
import json
import logging
import os
import sys
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ORCHESTRATOR_ROOT = os.path.join(PROJECT_ROOT, "orchestrator")
if ORCHESTRATOR_ROOT not in sys.path:
    sys.path.insert(0, ORCHESTRATOR_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.engine import SagaEngine
from app.core.enums import SagaStatus, StepStatus
from app.core.workflow import create_order_workflow
from app.messaging.consumer import RepliesConsumer
from app.models.saga import Saga, SagaStep


class _NullContextManager:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockSessionWithLock:
    """Mock de sessão com rastreamento de locks (FOR UPDATE)."""

    def __init__(self):
        self._sagas: dict[str, Saga] = {}
        self.locked_steps: list[str] = []
        self.for_update_calls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def add(self, obj):
        pass

    def begin(self):
        return _NullContextManager()

    def put_saga(self, saga: Saga):
        self._sagas[str(saga.id)] = saga

    def get_saga(self, saga_id: str):
        return self._sagas.get(saga_id)

    async def lock_step(self, command_id: str):
        self.locked_steps.append(command_id)
        return None


class MockPublisher:
    def __init__(self):
        self.commands: list[dict] = []

    def publish_command(self, service, command_type, saga_id, command_id, attempt, payload):
        self.commands.append({
            "service": service,
            "command_type": command_type,
            "saga_id": saga_id,
            "command_id": command_id,
            "attempt": attempt,
            "payload": payload,
        })


def _setup_engine_and_saga(step_0_status=StepStatus.COMPLETED):
    workflow = create_order_workflow(step_timeout_seconds=0, step_max_attempts=3)
    publisher = MockPublisher()
    engine = SagaEngine(workflow=workflow, publisher=publisher)
    session = MockSessionWithLock()

    saga_id = uuid.uuid4()
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    saga = Saga(
        id=saga_id,
        order_id="ORD-DUP-01",
        status=SagaStatus.RUNNING,
        current_step_index=1 if step_0_status == StepStatus.COMPLETED else 0,
        payload={"order_id": "ORD-DUP-01"},
        created_at=now,
        updated_at=now,
    )

    cmd_id_0 = str(uuid.uuid4())
    step_0 = SagaStep(
        id=uuid.uuid4(),
        saga_id=saga_id,
        step_name="inventory",
        step_index=0,
        status=step_0_status,
        command_id=cmd_id_0,
        attempts=1,
        payload={"order_id": "ORD-DUP-01"},
        result={"reserved": True} if step_0_status == StepStatus.COMPLETED else {},
    )
    step_0.saga = saga

    cmd_id_1 = str(uuid.uuid4())
    step_1 = SagaStep(
        id=uuid.uuid4(),
        saga_id=saga_id,
        step_name="payment",
        step_index=1,
        status=StepStatus.RUNNING if step_0_status == StepStatus.COMPLETED else StepStatus.PENDING,
        command_id=cmd_id_1,
        attempts=1,
        payload={"order_id": "ORD-DUP-01"},
        result={},
    )
    step_1.saga = saga

    saga.steps = [step_0, step_1]
    saga.events = []
    session.put_saga(saga)

    return engine, session, saga, step_0, publisher


class TestDuplicateRepliesProtection(unittest.IsolatedAsyncioTestCase):
    """Testa a proteção e lock contra replies duplicadas no handle_reply."""

    async def test_lock_step_executado_no_handle_reply(self):
        """SELECT FOR UPDATE deve ser invocado para o command_id."""
        engine, session, saga, step_0, publisher = _setup_engine_and_saga(StepStatus.RUNNING)

        reply = {
            "command_id": step_0.command_id,
            "saga_id": str(saga.id),
            "command_type": "ReservarEstoque",
            "success": True,
            "payload": {"reserved": True},
        }

        await engine.handle_reply(reply, session=session)
        self.assertIn(step_0.command_id, session.locked_steps)

    async def test_reply_duplicada_step_completed_emite_log_e_ignora(self):
        """Reply para step já COMPLETED deve registrar 'duplicate reply ignored' e não publicar."""
        engine, session, saga, step_0, publisher = _setup_engine_and_saga(StepStatus.COMPLETED)

        reply = {
            "command_id": step_0.command_id,
            "saga_id": str(saga.id),
            "command_type": "ReservarEstoque",
            "success": True,
            "payload": {"reserved": True},
        }

        with self.assertLogs("saga-engine", level="INFO") as log_capture:
            await engine.handle_reply(reply, session=session)

        # Confirma a mensagem explícita no log
        log_text = " ".join(log_capture.output)
        self.assertIn("duplicate reply ignored", log_text)
        self.assertIn(step_0.command_id, log_text)

        # Não deve haver novas publicações além do que já existia
        self.assertEqual(len(publisher.commands), 0)

        # O estado da Saga não deve ser alterado
        self.assertEqual(saga.current_step_index, 1)

    async def test_reply_duplicada_step_compensated_emite_log_e_ignora(self):
        """Reply para step já COMPENSATED deve registrar 'duplicate reply ignored'."""
        engine, session, saga, step_0, publisher = _setup_engine_and_saga(StepStatus.COMPENSATED)
        saga.status = SagaStatus.COMPENSATING

        reply_comp = {
            "command_id": step_0.command_id,
            "saga_id": str(saga.id),
            "command_type": "LiberarEstoque",
            "success": True,
            "payload": {"released": True},
        }

        with self.assertLogs("saga-engine", level="INFO") as log_capture:
            await engine.handle_reply(reply_comp, session=session)

        log_text = " ".join(log_capture.output)
        self.assertIn("duplicate reply ignored", log_text)
        self.assertEqual(len(publisher.commands), 0)

    async def test_consumer_faz_ack_mesmo_com_reply_duplicada(self):
        """O RepliesConsumer deve enviar ACK na mensagem RabbitMQ mesmo quando duplicada."""
        engine, session, saga, step_0, publisher = _setup_engine_and_saga(StepStatus.COMPLETED)

        # Força o engine a usar a sessão do teste
        engine.session_factory = lambda: session

        consumer = RepliesConsumer(channel=MagicMock(), engine=engine)

        mock_msg = MagicMock()
        mock_msg.body = json.dumps({
            "command_id": step_0.command_id,
            "saga_id": str(saga.id),
            "command_type": "ReservarEstoque",
            "success": True,
            "payload": {},
        }).encode("utf-8")
        mock_msg.ack = AsyncMock()
        mock_msg.nack = AsyncMock()

        await consumer.process_message(mock_msg)

        # Deve chamar ACK e nunca NACK
        mock_msg.ack.assert_awaited_once()
        mock_msg.nack.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
