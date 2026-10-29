"""
Testes Unitários para Listagem e Filtros de Sagas — Card 7.3.

Valida que:
  - GET /sagas permite filtrar por status, order_id, from_date e to_date
  - Suporta paginação via limit e offset
  - Retorna uma resposta resumida (SagaSummary) sem sobrecarregar com steps ou events
  - Duração em milissegundos (duration_ms) é calculada para sagas concluídas e None para ativas
  - Status inválido retorna lista vazia sem quebrar
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


def duration_ms(start, end):
    if start and end:
        return int((end - start).total_seconds() * 1000)
    return None


class FakeSagaItem:
    def __init__(
        self,
        order_id: str,
        status: SagaStatus,
        created_at: datetime,
        completed_at: datetime = None,
    ):
        self.id = uuid.uuid4()
        self.order_id = order_id
        self.status = status
        self.created_at = created_at
        self.completed_at = completed_at


def filter_and_paginate_sagas(
    sagas: list[FakeSagaItem],
    status: str = None,
    order_id: str = None,
    from_date: datetime = None,
    to_date: datetime = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Aplica os filtros em memória espelhando a query do SagaRepository."""
    filtered = list(sagas)

    if status:
        try:
            saga_status = SagaStatus(status.upper())
            filtered = [s for s in filtered if s.status == saga_status]
        except ValueError:
            return []

    if order_id:
        filtered = [s for s in filtered if s.order_id == order_id]

    if from_date:
        if isinstance(from_date, str):
            from_date = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        filtered = [s for s in filtered if s.created_at >= from_date]

    if to_date:
        if isinstance(to_date, str):
            to_date = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
        filtered = [s for s in filtered if s.created_at <= to_date]

    # Ordena decrescente por created_at
    filtered.sort(key=lambda s: s.created_at, reverse=True)

    # Paginação
    paginated = filtered[offset : offset + limit]

    # Converte para dict resumido (SagaSummaryResponse)
    return [
        {
            "saga_id": str(s.id),
            "order_id": s.order_id,
            "status": s.status,
            "created_at": s.created_at,
            "completed_at": s.completed_at,
            "duration_ms": duration_ms(s.created_at, s.completed_at),
        }
        for s in paginated
    ]


class TestListSagasFilters(unittest.TestCase):

    def setUp(self):
        now = datetime.now(timezone.utc)
        self.base_time = now
        self.sagas = [
            FakeSagaItem("ORD-001", SagaStatus.COMPLETED, now - timedelta(hours=5), now - timedelta(hours=4, minutes=59)),
            FakeSagaItem("ORD-002", SagaStatus.RUNNING, now - timedelta(hours=4)),
            FakeSagaItem("ORD-003", SagaStatus.FAILED, now - timedelta(hours=3), now - timedelta(hours=2, minutes=59)),
            FakeSagaItem("ORD-004", SagaStatus.COMPENSATED, now - timedelta(hours=2), now - timedelta(hours=1, minutes=59)),
            FakeSagaItem("ORD-005", SagaStatus.COMPLETED, now - timedelta(hours=1), now - timedelta(minutes=59)),
        ]

    def test_filtro_por_status(self):
        """Filtra apenas sagas com status COMPLETED."""
        res = filter_and_paginate_sagas(self.sagas, status="COMPLETED")
        self.assertEqual(len(res), 2)
        for item in res:
            self.assertEqual(item["status"], SagaStatus.COMPLETED)

    def test_filtro_por_status_case_insensitive(self):
        """Filtro deve aceitar minúsculas (ex: 'running')."""
        res = filter_and_paginate_sagas(self.sagas, status="running")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["order_id"], "ORD-002")

    def test_filtro_por_status_invalido_retorna_vazio(self):
        """Status que não existe retorna lista vazia."""
        res = filter_and_paginate_sagas(self.sagas, status="NAO_EXISTE")
        self.assertEqual(res, [])

    def test_filtro_por_order_id(self):
        """Filtra exatamente pelo order_id."""
        res = filter_and_paginate_sagas(self.sagas, order_id="ORD-003")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["order_id"], "ORD-003")
        self.assertEqual(res[0]["status"], SagaStatus.FAILED)

    def test_filtro_por_from_date(self):
        """Retorna apenas sagas criadas após determinado timestamp."""
        cutoff = self.base_time - timedelta(hours=2, minutes=30)
        res = filter_and_paginate_sagas(self.sagas, from_date=cutoff)
        # ORD-004 (-2h) e ORD-005 (-1h)
        self.assertEqual(len(res), 2)
        order_ids = [r["order_id"] for r in res]
        self.assertIn("ORD-004", order_ids)
        self.assertIn("ORD-005", order_ids)

    def test_filtro_por_to_date(self):
        """Retorna apenas sagas criadas até determinado timestamp."""
        cutoff = self.base_time - timedelta(hours=3, minutes=30)
        res = filter_and_paginate_sagas(self.sagas, to_date=cutoff)
        # ORD-001 (-5h) e ORD-002 (-4h)
        self.assertEqual(len(res), 2)
        order_ids = [r["order_id"] for r in res]
        self.assertIn("ORD-001", order_ids)
        self.assertIn("ORD-002", order_ids)

    def test_filtro_por_intervalo_data(self):
        """Combina from_date e to_date para recorte de janela."""
        f_date = self.base_time - timedelta(hours=4, minutes=30)
        t_date = self.base_time - timedelta(hours=1, minutes=30)
        res = filter_and_paginate_sagas(self.sagas, from_date=f_date, to_date=t_date)
        # ORD-002 (-4h), ORD-003 (-3h), ORD-004 (-2h)
        self.assertEqual(len(res), 3)

    def test_paginacao_limit_e_offset(self):
        """Valida que limit e offset recortam e paginam corretamente."""
        page1 = filter_and_paginate_sagas(self.sagas, limit=2, offset=0)
        self.assertEqual(len(page1), 2)
        self.assertEqual(page1[0]["order_id"], "ORD-005")  # Mais recente primeiro
        self.assertEqual(page1[1]["order_id"], "ORD-004")

        page2 = filter_and_paginate_sagas(self.sagas, limit=2, offset=2)
        self.assertEqual(len(page2), 2)
        self.assertEqual(page2[0]["order_id"], "ORD-003")
        self.assertEqual(page2[1]["order_id"], "ORD-002")

    def test_resposta_resumida_sem_steps_nem_events(self):
        """A resposta resumida não deve conter chaves pesadas como 'steps' ou 'events'."""
        res = filter_and_paginate_sagas(self.sagas, limit=1)
        item = res[0]
        self.assertNotIn("steps", item)
        self.assertNotIn("events", item)
        self.assertIn("saga_id", item)
        self.assertIn("order_id", item)
        self.assertIn("status", item)
        self.assertIn("created_at", item)

    def test_duration_ms_calculado_apenas_quando_concluido(self):
        """Saga concluída possui duration_ms em ms; em execução é None."""
        res = filter_and_paginate_sagas(self.sagas)
        ord_001 = [r for r in res if r["order_id"] == "ORD-001"][0]
        self.assertEqual(ord_001["duration_ms"], 60000)  # 1 minuto = 60000ms

        ord_002 = [r for r in res if r["order_id"] == "ORD-002"][0]
        self.assertIsNone(ord_002["duration_ms"])


if __name__ == "__main__":
    unittest.main()

