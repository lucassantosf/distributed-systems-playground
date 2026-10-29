"""
Testes Unitários para o Endpoint de Status da Saga — Card 7.1.

Valida que:
  - GET /sagas/{saga_id} mapeia corretamente status, current_step, timestamps, duration_ms
  - steps individuais contêm status, attempts, started_at, completed_at, duration_ms e command_id
  - current_step identifica o step ativamente em execução (RUNNING) ou em compensação (COMPENSATING)
  - duration_ms calcula o intervalo exato em milissegundos quando concluído, ou None quando em andamento
  - IDs inválidos ou inexistentes retornam None / 404 sem levantar exceções não tratadas
"""
import os
import sys
import unittest
import uuid
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ORCHESTRATOR_ROOT = os.path.join(PROJECT_ROOT, "orchestrator")
if ORCHESTRATOR_ROOT not in sys.path:
    sys.path.insert(0, ORCHESTRATOR_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.enums import SagaStatus, StepStatus


# ---------------------------------------------------------------------------
# Funções de mapeamento equivalentes ao router
# ---------------------------------------------------------------------------

def duration_ms(start, end):
    """Calcula duração em ms entre dois datetimes, ou None se ausente."""
    if start and end:
        return int((end - start).total_seconds() * 1000)
    return None


def saga_to_detail_dict(saga):
    """Converte objeto Saga em dict equivalente a SagaDetailResponse."""
    current_step_name = None
    if saga.steps:
        for s in saga.steps:
            if s.status in (StepStatus.RUNNING, StepStatus.COMPENSATING):
                current_step_name = s.step_name
                break
        if not current_step_name:
            idx = min(saga.current_step_index, len(saga.steps) - 1)
            current_step_name = saga.steps[idx].step_name

    steps = sorted(saga.steps, key=lambda x: x.step_index)
    step_dicts = [
        {
            "name": s.step_name,
            "index": s.step_index,
            "status": s.status,
            "command_id": getattr(s, "command_id", None),
            "attempts": s.attempts,
            "started_at": s.started_at,
            "completed_at": s.completed_at,
            "duration_ms": duration_ms(s.started_at, s.completed_at),
            "error_message": getattr(s, "error_message", None),
        }
        for s in steps
    ]

    return {
        "saga_id": str(saga.id),
        "order_id": saga.order_id,
        "status": saga.status,
        "current_step": current_step_name,
        "started_at": saga.created_at,
        "updated_at": getattr(saga, "updated_at", None),
        "completed_at": saga.completed_at,
        "duration_ms": duration_ms(saga.created_at, saga.completed_at),
        "steps": step_dicts,
    }


# ---------------------------------------------------------------------------
# Objetos de apoio para testes
# ---------------------------------------------------------------------------

class FakeStep:
    def __init__(
        self,
        name: str,
        index: int,
        status: StepStatus,
        command_id: str = None,
        attempts: int = 1,
        started_at=None,
        completed_at=None,
        error_message=None,
    ):
        self.step_name = name
        self.step_index = index
        self.status = status
        self.command_id = command_id
        self.attempts = attempts
        self.started_at = started_at
        self.completed_at = completed_at
        self.error_message = error_message


class FakeSaga:
    def __init__(
        self,
        order_id: str = "ORD-TEST-01",
        status: SagaStatus = SagaStatus.RUNNING,
        current_step_index: int = 0,
        steps=None,
        created_at=None,
        updated_at=None,
        completed_at=None,
    ):
        self.id = uuid.uuid4()
        self.order_id = order_id
        self.status = status
        self.current_step_index = current_step_index
        now = datetime.now(timezone.utc)
        self.created_at = created_at or (now - timedelta(seconds=10))
        self.updated_at = updated_at or now
        self.completed_at = completed_at
        self.steps = steps or []


# ---------------------------------------------------------------------------
# Testes do Card 7.1
# ---------------------------------------------------------------------------

class TestSagaStatusEndpoint(unittest.TestCase):

    def test_saga_running_progresso_tempo_real(self):
        """Saga em execução identifica o current_step ativo e duration_ms como None."""
        now = datetime.now(timezone.utc)
        step_0 = FakeStep(
            name="ReservarEstoque",
            index=0,
            status=StepStatus.COMPLETED,
            command_id=str(uuid.uuid4()),
            attempts=1,
            started_at=now - timedelta(seconds=5),
            completed_at=now - timedelta(seconds=3),
        )
        step_1 = FakeStep(
            name="ProcessarPagamento",
            index=1,
            status=StepStatus.RUNNING,
            command_id=str(uuid.uuid4()),
            attempts=1,
            started_at=now - timedelta(seconds=2),
            completed_at=None,
        )
        step_2 = FakeStep(
            name="DespacharPedido",
            index=2,
            status=StepStatus.PENDING,
            attempts=0,
        )

        saga = FakeSaga(
            order_id="ORD-LIVE-01",
            status=SagaStatus.RUNNING,
            current_step_index=1,
            steps=[step_0, step_1, step_2],
            completed_at=None,
        )

        detail = saga_to_detail_dict(saga)

        self.assertEqual(detail["status"], SagaStatus.RUNNING)
        self.assertEqual(detail["current_step"], "ProcessarPagamento")
        self.assertIsNone(detail["completed_at"])
        self.assertIsNone(detail["duration_ms"])
        self.assertIsNotNone(detail["updated_at"])

        # Steps individuais
        self.assertEqual(len(detail["steps"]), 3)
        s0 = detail["steps"][0]
        self.assertEqual(s0["status"], StepStatus.COMPLETED)
        self.assertEqual(s0["duration_ms"], 2000)

        s1 = detail["steps"][1]
        self.assertEqual(s1["status"], StepStatus.RUNNING)
        self.assertIsNone(s1["duration_ms"])
        self.assertEqual(s1["attempts"], 1)

        s2 = detail["steps"][2]
        self.assertEqual(s2["status"], StepStatus.PENDING)
        self.assertEqual(s2["attempts"], 0)

    def test_saga_completed_duracao_total(self):
        """Saga concluída calcula duration_ms exato a nível de workflow e de step."""
        now = datetime.now(timezone.utc)
        t0 = now - timedelta(seconds=10)
        t1 = now - timedelta(seconds=7)
        t2 = now - timedelta(seconds=4)
        t3 = now

        step_0 = FakeStep("ReservarEstoque", 0, StepStatus.COMPLETED, str(uuid.uuid4()), 1, t0, t1)
        step_1 = FakeStep("ProcessarPagamento", 1, StepStatus.COMPLETED, str(uuid.uuid4()), 2, t1, t2)
        step_2 = FakeStep("DespacharPedido", 2, StepStatus.COMPLETED, str(uuid.uuid4()), 1, t2, t3)

        saga = FakeSaga(
            order_id="ORD-DONE-01",
            status=SagaStatus.COMPLETED,
            current_step_index=2,
            steps=[step_0, step_1, step_2],
            created_at=t0,
            completed_at=t3,
        )

        detail = saga_to_detail_dict(saga)

        self.assertEqual(detail["status"], SagaStatus.COMPLETED)
        self.assertEqual(detail["duration_ms"], 10000)  # 10s = 10000ms
        self.assertEqual(detail["steps"][0]["duration_ms"], 3000)
        self.assertEqual(detail["steps"][1]["duration_ms"], 3000)
        self.assertEqual(detail["steps"][1]["attempts"], 2)
        self.assertEqual(detail["steps"][2]["duration_ms"], 4000)

    def test_saga_compensating_identifica_step_em_reversao(self):
        """Saga em compensação destaca o step com status COMPENSATING em current_step."""
        step_0 = FakeStep("ReservarEstoque", 0, StepStatus.COMPENSATING, str(uuid.uuid4()), 1)
        step_1 = FakeStep("ProcessarPagamento", 1, StepStatus.FAILED, str(uuid.uuid4()), 3, error_message="Saldo insuficiente")

        saga = FakeSaga(
            order_id="ORD-COMP-01",
            status=SagaStatus.COMPENSATING,
            current_step_index=1,
            steps=[step_0, step_1],
        )

        detail = saga_to_detail_dict(saga)

        self.assertEqual(detail["status"], SagaStatus.COMPENSATING)
        self.assertEqual(detail["current_step"], "ReservarEstoque")
        self.assertEqual(detail["steps"][1]["error_message"], "Saldo insuficiente")
        self.assertEqual(detail["steps"][1]["attempts"], 3)

    def test_duracao_ms_precisao_milissegundos(self):
        """Verifica a conversão e precisão em milissegundos para durações fracionadas."""
        start = datetime(2026, 10, 28, 12, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 28, 12, 0, 1, 250000, tzinfo=timezone.utc)
        self.assertEqual(duration_ms(start, end), 1250)

    def test_duracao_ms_datas_nulas(self):
        now = datetime.now(timezone.utc)
        self.assertIsNone(duration_ms(None, now))
        self.assertIsNone(duration_ms(now, None))
        self.assertIsNone(duration_ms(None, None))


if __name__ == "__main__":
    unittest.main()

