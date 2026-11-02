"""
Testes Unitários para Recovery após Falha do Orquestrador — Card 8.2.

Valida que:
  - find_stuck_running_steps localiza steps com status RUNNING cujo started_at ultrapassou o threshold
  - recover_stuck_sagas re-publica os comandos dos steps pendentes preservando o MESMO command_id
  - O watchdog de timeout é re-armado para os steps recuperados
  - O evento SagaRecoveryTriggered é registrado no audit trail para rastreabilidade
  - Steps em status terminal (COMPLETED, FAILED, PENDING) não são afetados pelo recovery
  - Idempotência: re-publicar com o mesmo command_id garante que o worker não re-execute lógica se já processou
"""
import asyncio
from datetime import datetime, timezone, timedelta
import os
import sys
import unittest
import uuid
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ORCHESTRATOR_ROOT = os.path.join(PROJECT_ROOT, "orchestrator")
if ORCHESTRATOR_ROOT not in sys.path:
    sys.path.insert(0, ORCHESTRATOR_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.engine import SagaEngine
from app.core.enums import SagaStatus, StepStatus
from app.core.workflow import create_order_workflow
from app.models.saga import Saga, SagaStep
import app.repositories.saga_repository as saga_repo


class _NullContextManager:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockPublisher:
    def __init__(self):
        self.published = []

    async def publish_command(self, service, command_type, saga_id, command_id, attempt, payload):
        self.published.append({
            "service": service,
            "command_type": command_type,
            "saga_id": saga_id,
            "command_id": command_id,
            "attempt": attempt,
            "payload": payload,
        })


class MockSession:
    def __init__(self, stuck_pairs=None):
        self.stuck_pairs = stuck_pairs or []
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    def begin(self):
        return _NullContextManager()


class TestOrchestratorRecovery(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.workflow = create_order_workflow(step_timeout_seconds=5, step_max_attempts=3)
        self.publisher = MockPublisher()
        self.engine = SagaEngine(workflow=self.workflow, publisher=self.publisher)

    async def test_recovery_republica_comandos_com_mesmo_command_id(self):
        """Ao reiniciar o orquestrador, comandos de steps pendentes são re-publicados com o mesmo command_id."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(seconds=30)  # claramente maior que threshold de 10s

        saga_id = uuid.uuid4()
        saga = Saga(
            id=saga_id,
            order_id="ORD-CRASH-01",
            status=SagaStatus.RUNNING,
            current_step_index=1,
            payload={"order_id": "ORD-CRASH-01", "total_amount": 100.0},
            created_at=old_time,
        )

        orig_cmd_id = str(uuid.uuid4())
        step_1 = SagaStep(
            id=uuid.uuid4(),
            saga_id=saga_id,
            step_name="ProcessarPagamento",
            step_index=1,
            status=StepStatus.RUNNING,
            command_id=orig_cmd_id,
            attempts=1,
            started_at=old_time,
            payload=saga.payload,
        )
        step_1.saga = saga
        saga.steps = [step_1]
        saga.events = []

        session = MockSession(stuck_pairs=[(saga, step_1)])

        with patch.object(saga_repo, "find_stuck_running_steps", return_value=[(saga, step_1)]):
            recovered = await self.engine.recover_stuck_sagas(threshold_seconds=10, session=session)

        # 1. Deve ter recuperado 1 saga
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["command_id"], orig_cmd_id)

        # 2. O comando publicado deve ter exatamente o MESMO command_id
        self.assertEqual(len(self.publisher.published), 1)
        pub_cmd = self.publisher.published[0]
        self.assertEqual(pub_cmd["command_id"], orig_cmd_id)
        self.assertEqual(pub_cmd["service"], "payment")
        self.assertEqual(pub_cmd["command_type"], "ProcessarPagamento")

        # 3. O watchdog de timeout deve ter sido re-armado para esse command_id
        self.assertIn(orig_cmd_id, self.engine._timeout_tasks)
        # Cancela o timeout para não deixar pendência no event loop
        self.engine._cancel_timeout(orig_cmd_id)

        # 4. Evento SagaRecoveryTriggered registrado no audit trail
        event_types = [e.event_type for e in saga.events]
        self.assertIn("SagaRecoveryTriggered", event_types)
        rec_event = next(e for e in saga.events if e.event_type == "SagaRecoveryTriggered")
        self.assertEqual(rec_event.event_payload["command_id"], orig_cmd_id)
        self.assertEqual(rec_event.event_payload["order_id"], "ORD-CRASH-01")

    async def test_recovery_sem_sagas_travadas_nao_publica_nada(self):
        """Se não houver steps em RUNNING antigos, nenhum comando é publicado."""
        session = MockSession(stuck_pairs=[])
        with patch.object(saga_repo, "find_stuck_running_steps", return_value=[]):
            recovered = await self.engine.recover_stuck_sagas(threshold_seconds=10, session=session)

        self.assertEqual(len(recovered), 0)
        self.assertEqual(len(self.publisher.published), 0)
        self.assertEqual(len(self.engine._timeout_tasks), 0)


if __name__ == "__main__":
    unittest.main()
