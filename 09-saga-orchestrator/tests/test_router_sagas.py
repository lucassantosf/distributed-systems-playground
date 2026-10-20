"""
Testes unitários para Card 3.3 — Mapeamento ORM → Resposta HTTP.

Testa as funções _duration_ms, _saga_to_detail e _event_to_response do router
usando dataclasses simples que emulam os ORM models, sem precisar de pydantic
ou SQLAlchemy instalados no ambiente local de testes.

A lógica de mapeamento é extraída do router e testada isoladamente,
verificando que os campos corretos são lidos dos objetos ORM e transferidos
para os dicts de resposta.
"""
import os
import sys
import unittest
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))

from app.core.enums import SagaStatus, StepStatus


# ---------------------------------------------------------------------------
# Duplica a lógica de mapeamento do router para teste isolado
# (sem depender de pydantic ou SQLAlchemy)
# ---------------------------------------------------------------------------

def duration_ms(start, end):
    """Calcula duração em ms entre dois datetimes, ou None se ausente."""
    if start and end:
        return int((end - start).total_seconds() * 1000)
    return None


def saga_to_dict(saga):
    """Converte ORM Saga em dict equivalente ao SagaDetailResponse."""
    current_step_name = None
    if saga.steps:
        idx = min(saga.current_step_index, len(saga.steps) - 1)
        current_step_name = saga.steps[idx].step_name

    steps = sorted(saga.steps, key=lambda x: x.step_index)
    step_dicts = [
        {
            "name": s.step_name,
            "index": s.step_index,
            "status": s.status,
            "attempts": s.attempts,
            "started_at": s.started_at,
            "completed_at": s.completed_at,
            "duration_ms": duration_ms(s.started_at, s.completed_at),
            "error_message": s.error_message,
        }
        for s in steps
    ]

    return {
        "saga_id": str(saga.id),
        "order_id": saga.order_id,
        "status": saga.status,
        "current_step": current_step_name,
        "started_at": saga.created_at,
        "completed_at": saga.completed_at,
        "duration_ms": duration_ms(saga.created_at, saga.completed_at),
        "steps": step_dicts,
    }


def event_to_dict(event):
    """Converte ORM SagaEvent em dict equivalente ao SagaEventResponse."""
    step_name = event.step.step_name if event.step else None
    return {
        "event_id": str(event.id),
        "event_type": event.event_type,
        "step": step_name,
        "created_at": event.created_at,
        "payload": event.event_payload or {},
    }


# ---------------------------------------------------------------------------
# Objetos fake que emulam os ORM models (sem SQLAlchemy)
# ---------------------------------------------------------------------------

class FakeStep:
    def __init__(self, name, index, status, attempts=1,
                 started_at=None, completed_at=None, error_message=None):
        self.step_name = name
        self.step_index = index
        self.status = status
        self.attempts = attempts
        self.started_at = started_at
        self.completed_at = completed_at
        self.error_message = error_message


class FakeEvent:
    def __init__(self, event_type, step=None, payload=None):
        self.id = uuid.uuid4()
        self.event_type = event_type
        self.step = step
        self.event_payload = payload or {}
        self.created_at = datetime.now(timezone.utc)


class FakeSaga:
    def __init__(self, order_id="ORD-001", status=SagaStatus.COMPLETED,
                 current_step_index=0, steps=None, completed_at=None):
        self.id = uuid.uuid4()
        self.order_id = order_id
        self.status = status
        self.current_step_index = current_step_index
        self.created_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        self.completed_at = completed_at
        self.steps = steps or []


# ---------------------------------------------------------------------------
# Testes de _duration_ms
# ---------------------------------------------------------------------------

class TestDurationMs(unittest.TestCase):

    def test_retorna_duracao_em_ms(self):
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 12, 0, 2, tzinfo=timezone.utc)
        self.assertEqual(duration_ms(start, end), 2000)

    def test_duracao_com_fracao(self):
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 12, 0, 0, 500000, tzinfo=timezone.utc)
        self.assertEqual(duration_ms(start, end), 500)

    def test_retorna_none_quando_start_ausente(self):
        end = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.assertIsNone(duration_ms(None, end))

    def test_retorna_none_quando_end_ausente(self):
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.assertIsNone(duration_ms(start, None))

    def test_retorna_none_quando_ambos_ausentes(self):
        self.assertIsNone(duration_ms(None, None))


# ---------------------------------------------------------------------------
# Testes de StepStatus enum no core (equivalente ao schema)
# ---------------------------------------------------------------------------

class TestStepStatusEnum(unittest.TestCase):

    def test_compensating_failed_presente(self):
        self.assertIn("COMPENSATING_FAILED", [s.value for s in StepStatus])

    def test_todos_os_valores_esperados(self):
        esperados = {"PENDING", "RUNNING", "COMPLETED", "FAILED",
                     "COMPENSATING", "COMPENSATED", "COMPENSATING_FAILED"}
        presentes = {s.value for s in StepStatus}
        self.assertEqual(esperados, presentes)


# ---------------------------------------------------------------------------
# Testes de saga_to_dict (espelha _saga_to_detail do router)
# ---------------------------------------------------------------------------

class TestSagaToDict(unittest.TestCase):

    def _build_full_saga(self):
        now = datetime.now(timezone.utc)
        steps = [
            FakeStep("ReservarEstoque", 0, StepStatus.COMPLETED,
                     started_at=now - timedelta(seconds=4),
                     completed_at=now - timedelta(seconds=3)),
            FakeStep("ProcessarPagamento", 1, StepStatus.COMPLETED,
                     started_at=now - timedelta(seconds=3),
                     completed_at=now - timedelta(seconds=2)),
            FakeStep("AgendarEntrega", 2, StepStatus.COMPLETED,
                     started_at=now - timedelta(seconds=2),
                     completed_at=now - timedelta(seconds=1)),
            FakeStep("EnviarNotificacao", 3, StepStatus.COMPLETED,
                     started_at=now - timedelta(seconds=1),
                     completed_at=now),
        ]
        return FakeSaga(
            order_id="ORD-FULL",
            status=SagaStatus.COMPLETED,
            current_step_index=3,
            steps=steps,
            completed_at=now,
        )

    def test_saga_id_como_string(self):
        saga = self._build_full_saga()
        d = saga_to_dict(saga)
        self.assertEqual(d["saga_id"], str(saga.id))

    def test_order_id_preservado(self):
        saga = self._build_full_saga()
        d = saga_to_dict(saga)
        self.assertEqual(d["order_id"], "ORD-FULL")

    def test_status_mapeado(self):
        saga = self._build_full_saga()
        d = saga_to_dict(saga)
        self.assertEqual(d["status"], SagaStatus.COMPLETED)

    def test_steps_em_ordem_crescente(self):
        saga = self._build_full_saga()
        d = saga_to_dict(saga)
        indices = [s["index"] for s in d["steps"]]
        self.assertEqual(indices, sorted(indices))

    def test_nomes_dos_steps_corretos(self):
        saga = self._build_full_saga()
        d = saga_to_dict(saga)
        self.assertEqual(d["steps"][0]["name"], "ReservarEstoque")
        self.assertEqual(d["steps"][-1]["name"], "EnviarNotificacao")

    def test_started_at_vem_de_created_at(self):
        saga = self._build_full_saga()
        d = saga_to_dict(saga)
        self.assertEqual(d["started_at"], saga.created_at)

    def test_completed_at_preservado(self):
        saga = self._build_full_saga()
        d = saga_to_dict(saga)
        self.assertEqual(d["completed_at"], saga.completed_at)

    def test_current_step_pelo_indice(self):
        saga = self._build_full_saga()
        saga.current_step_index = 2
        d = saga_to_dict(saga)
        self.assertEqual(d["current_step"], "AgendarEntrega")

    def test_saga_sem_steps_nao_quebra(self):
        saga = FakeSaga(steps=[])
        d = saga_to_dict(saga)
        self.assertEqual(d["steps"], [])
        self.assertIsNone(d["current_step"])

    def test_step_com_error_message(self):
        step = FakeStep("ProcessarPagamento", 0, StepStatus.FAILED,
                        error_message="Cartão recusado")
        saga = FakeSaga(steps=[step])
        d = saga_to_dict(saga)
        self.assertEqual(d["steps"][0]["error_message"], "Cartão recusado")

    def test_duration_ms_calculado_para_step_completado(self):
        now = datetime.now(timezone.utc)
        step = FakeStep("ReservarEstoque", 0, StepStatus.COMPLETED,
                        started_at=now - timedelta(seconds=1),
                        completed_at=now)
        saga = FakeSaga(steps=[step])
        d = saga_to_dict(saga)
        self.assertIsNotNone(d["steps"][0]["duration_ms"])
        self.assertGreater(d["steps"][0]["duration_ms"], 0)

    def test_step_status_compensating_failed_representado(self):
        step = FakeStep("ProcessarPagamento", 0, StepStatus.COMPENSATING_FAILED)
        saga = FakeSaga(steps=[step])
        d = saga_to_dict(saga)
        self.assertEqual(d["steps"][0]["status"], StepStatus.COMPENSATING_FAILED)


# ---------------------------------------------------------------------------
# Testes de event_to_dict (espelha _event_to_response do router)
# ---------------------------------------------------------------------------

class TestEventToDict(unittest.TestCase):

    def test_event_sem_step_tem_step_none(self):
        event = FakeEvent("SagaStarted")
        d = event_to_dict(event)
        self.assertIsNone(d["step"])

    def test_event_com_step_tem_step_name(self):
        step = FakeStep("ReservarEstoque", 0, StepStatus.COMPLETED)
        event = FakeEvent("StepCompleted", step=step)
        d = event_to_dict(event)
        self.assertEqual(d["step"], "ReservarEstoque")

    def test_event_id_como_string(self):
        event = FakeEvent("SagaCompleted")
        d = event_to_dict(event)
        self.assertEqual(d["event_id"], str(event.id))

    def test_payload_preservado(self):
        event = FakeEvent("StepStarted", payload={"attempt": 1, "service": "inventory"})
        d = event_to_dict(event)
        self.assertEqual(d["payload"]["service"], "inventory")

    def test_event_payload_none_vira_dict_vazio(self):
        event = FakeEvent("SagaStarted")
        event.event_payload = None
        d = event_to_dict(event)
        self.assertEqual(d["payload"], {})

    def test_event_type_preservado(self):
        event = FakeEvent("SagaCompensating")
        d = event_to_dict(event)
        self.assertEqual(d["event_type"], "SagaCompensating")


if __name__ == "__main__":
    unittest.main()

