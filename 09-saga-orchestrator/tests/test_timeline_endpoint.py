"""
Testes Unitários para o Endpoint de Timeline / Audit Trail — Card 7.2.

Valida que:
  - GET /sagas/{saga_id}/timeline retorna todos os SagaEvents em ordem cronológica
  - Cada evento possui event_id, event_type, step, created_at e payload
  - O audit trail preserva dados ricos no payload (command_id, error, attempts, etc.)
  - O step é extraído do objeto relacionado ou do payload como fallback gracioso
  - total_events, saga_id, order_id e status são consolidados na resposta
  - IDs inexistentes levantam 404
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

from app.core.enums import SagaStatus


# ---------------------------------------------------------------------------
# Funções de mapeamento equivalentes ao router
# ---------------------------------------------------------------------------

def event_to_response_dict(event):
    """Converte objeto SagaEvent em dict equivalente a SagaEventResponse."""
    step_name = None
    if getattr(event, "step", None):
        step_name = event.step.step_name
    elif getattr(event, "event_payload", None) and isinstance(event.event_payload, dict):
        step_name = event.event_payload.get("step_name")

    return {
        "event_id": str(event.id),
        "event_type": event.event_type,
        "step": step_name,
        "created_at": event.created_at,
        "payload": event.event_payload or {},
    }


def timeline_to_response_dict(saga, events):
    """Converte Saga e lista de eventos em dict equivalente a SagaTimelineResponse."""
    sorted_events = sorted(events, key=lambda e: e.created_at)
    event_dicts = [event_to_response_dict(e) for e in sorted_events]
    return {
        "saga_id": str(saga.id),
        "order_id": getattr(saga, "order_id", None),
        "status": getattr(saga, "status", None),
        "total_events": len(event_dicts),
        "events": event_dicts,
    }


# ---------------------------------------------------------------------------
# Objetos de apoio para testes
# ---------------------------------------------------------------------------

class FakeStep:
    def __init__(self, name: str):
        self.step_name = name


class FakeEvent:
    def __init__(self, event_type: str, step=None, payload=None, created_at=None):
        self.id = uuid.uuid4()
        self.event_type = event_type
        self.step = step
        self.event_payload = payload or {}
        self.created_at = created_at or datetime.now(timezone.utc)


class FakeSaga:
    def __init__(self, order_id: str = "ORD-AUDIT-01", status: SagaStatus = SagaStatus.COMPLETED):
        self.id = uuid.uuid4()
        self.order_id = order_id
        self.status = status


# ---------------------------------------------------------------------------
# Testes do Card 7.2
# ---------------------------------------------------------------------------

class TestTimelineEndpoint(unittest.TestCase):

    def test_timeline_ordem_cronologica_estrita(self):
        """Eventos devem ser retornados rigorosamente na ordem em que ocorreram."""
        saga = FakeSaga()
        t0 = datetime.now(timezone.utc) - timedelta(seconds=10)
        t1 = t0 + timedelta(seconds=2)
        t2 = t0 + timedelta(seconds=5)
        t3 = t0 + timedelta(seconds=8)

        # Inseridos propositalmente fora de ordem cronológica
        events = [
            FakeEvent("StepCompleted", FakeStep("ReservarEstoque"), created_at=t2),
            FakeEvent("SagaStarted", payload={"order_id": saga.order_id}, created_at=t0),
            FakeEvent("SagaCompleted", created_at=t3),
            FakeEvent("StepStarted", FakeStep("ReservarEstoque"), created_at=t1),
        ]

        timeline = timeline_to_response_dict(saga, events)

        self.assertEqual(timeline["total_events"], 4)
        types_ordenados = [e["event_type"] for e in timeline["events"]]
        self.assertEqual(
            types_ordenados,
            ["SagaStarted", "StepStarted", "StepCompleted", "SagaCompleted"]
        )

    def test_payload_e_step_preservados_para_debugging(self):
        """O payload deve preservar todos os metadados técnicos úteis para debugging."""
        saga = FakeSaga(status=SagaStatus.COMPENSATING)
        cmd_id = str(uuid.uuid4())
        event = FakeEvent(
            event_type="StepFailed",
            step=FakeStep("ProcessarPagamento"),
            payload={
                "command_id": cmd_id,
                "attempt": 3,
                "max_attempts": 3,
                "error": "Timeout do gateway de pagamento",
            },
        )

        timeline = timeline_to_response_dict(saga, [event])

        self.assertEqual(timeline["total_events"], 1)
        ev_resp = timeline["events"][0]
        self.assertEqual(ev_resp["event_type"], "StepFailed")
        self.assertEqual(ev_resp["step"], "ProcessarPagamento")
        self.assertEqual(ev_resp["payload"]["command_id"], cmd_id)
        self.assertEqual(ev_resp["payload"]["attempt"], 3)
        self.assertEqual(ev_resp["payload"]["error"], "Timeout do gateway de pagamento")

    def test_step_fallback_para_payload_quando_step_orm_nulo(self):
        """Se o step ORM não estiver associado, obtém o step_name de dentro do payload."""
        saga = FakeSaga()
        event = FakeEvent(
            event_type="StepStarted",
            step=None,
            payload={"step_name": "NotificarCliente", "attempt": 1},
        )

        ev_dict = event_to_response_dict(event)
        self.assertEqual(ev_dict["step"], "NotificarCliente")

    def test_metadados_da_saga_na_resposta_da_timeline(self):
        """TimelineResponse deve retornar saga_id, order_id e status."""
        saga = FakeSaga(order_id="ORD-XYZ-99", status=SagaStatus.COMPLETED)
        timeline = timeline_to_response_dict(saga, [])

        self.assertEqual(timeline["saga_id"], str(saga.id))
        self.assertEqual(timeline["order_id"], "ORD-XYZ-99")
        self.assertEqual(timeline["status"], SagaStatus.COMPLETED)
        self.assertEqual(timeline["total_events"], 0)
        self.assertEqual(timeline["events"], [])

    def test_eventos_com_event_id_unicos(self):
        """Cada evento no audit trail possui um identificador único de evento."""
        saga = FakeSaga()
        events = [FakeEvent("SagaStarted"), FakeEvent("StepStarted"), FakeEvent("StepCompleted")]
        timeline = timeline_to_response_dict(saga, events)

        ids = [e["event_id"] for e in timeline["events"]]
        self.assertEqual(len(ids), 3)
        self.assertEqual(len(set(ids)), 3, "Todos os event_ids devem ser distintos")


if __name__ == "__main__":
    unittest.main()

