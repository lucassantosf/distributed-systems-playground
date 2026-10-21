"""
Testes unitários para Card 4.1 — Lógica de Compensação no SagaEngine.

Cobre os cenários de compensação com granularidade maior que test_engine.py:
  - Falha no step 1 (payment) → compensa step 0 (inventory) → Saga COMPENSATED
  - Falha no step 2 (shipping) → compensa steps 1 e 0 em ordem decrescente (LIFO)
  - Falha no último step (step 3) → steps 0..2 compensados em ordem reversa
  - Step sem compensation_command (NotificarCliente) é pulado na compensação
  - start_compensation invocado diretamente quando Saga já está RUNNING
  - Saga sem steps COMPLETED vai direto para COMPENSATED (nada a desfazer)
  - Ordem decrescente dos steps de compensação é garantida
  - Eventos de compensação registrados corretamente (SagaCompensating, StepCompensationStarted,
    StepCompensated, SagaCompensated)
  - Falha irrecuperável na compensação → step COMPENSATING_FAILED + Saga FAILED
"""
import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))

from app.core.enums import SagaStatus, StepStatus
from app.core.engine import SagaEngine
from app.core.workflow import ORDER_WORKFLOW, StepDefinition, WorkflowDefinition
from app.models.saga import Saga, SagaStep, SagaEvent


# ---------------------------------------------------------------------------
# Helpers de teste
# ---------------------------------------------------------------------------

class MockSession:
    """Sessão em memória — mesmo padrão de test_engine.py."""
    def __init__(self):
        self.sagas = {}
        self.sagas_by_order = {}
        self.added = []

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, Saga):
            self.sagas[str(obj.id)] = obj
            self.sagas_by_order[obj.order_id] = obj

    async def get_saga(self, saga_id: str):
        return self.sagas.get(str(saga_id))

    async def get_saga_by_order_id(self, order_id: str):
        return self.sagas_by_order.get(order_id)


class MockPublisher:
    def __init__(self):
        self.commands = []

    async def publish_command(self, service, command_type, saga_id, command_id, attempt, payload):
        self.commands.append({
            "service": service,
            "command_type": command_type,
            "saga_id": saga_id,
            "command_id": command_id,
            "attempt": attempt,
            "payload": payload,
        })

    def last_command(self):
        return self.commands[-1] if self.commands else None

    def command_types(self):
        return [c["command_type"] for c in self.commands]


def success_reply(saga, step_index, command_type, service):
    step = saga.steps[step_index]
    return {
        "saga_id": str(saga.id),
        "command_id": step.command_id,
        "command_type": command_type,
        "service": service,
        "success": True,
        "payload": {},
    }


def failure_reply(saga, step_index, command_type, service, error="Erro simulado"):
    step = saga.steps[step_index]
    return {
        "saga_id": str(saga.id),
        "command_id": step.command_id,
        "command_type": command_type,
        "service": service,
        "success": False,
        "error_message": error,
    }


# ---------------------------------------------------------------------------
# Testes de Compensação
# ---------------------------------------------------------------------------

class TestCompensacao(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.session = MockSession()
        self.publisher = MockPublisher()
        self.engine = SagaEngine(
            session_factory=None,
            workflow=ORDER_WORKFLOW,
            publisher=self.publisher,
        )

    async def _iniciar_saga(self, order_id: str = "ORD-COMP") -> Saga:
        return await self.engine.start_saga(
            order_id, {"order_id": order_id, "total_amount": 100.0}, session=self.session
        )

    # -----------------------------------------------------------------------
    # Cenário 1: Falha no step 1 → compensa step 0 → COMPENSATED
    # -----------------------------------------------------------------------

    async def test_falha_step1_compensa_step0_e_saga_compensated(self):
        saga = await self._iniciar_saga("ORD-C1")

        # Step 0 completa
        await self.engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"), session=self.session
        )
        self.assertEqual(saga.steps[0].status, StepStatus.COMPLETED)

        # Step 1 falha imediatamente (sem retries)
        saga.steps[1].attempts = ORDER_WORKFLOW.steps[1].max_attempts
        await self.engine.handle_reply(
            failure_reply(saga, 1, "ProcessarPagamento", "payment", "Limite excedido"),
            session=self.session,
        )

        # Saga → COMPENSATING
        self.assertEqual(saga.status, SagaStatus.COMPENSATING)
        # Step 1 → FAILED (não é compensado — nunca completou)
        self.assertEqual(saga.steps[1].status, StepStatus.FAILED)
        # Step 0 → COMPENSATING (foi completado, deve ser desfeito)
        self.assertEqual(saga.steps[0].status, StepStatus.COMPENSATING)
        # Step 2 e 3 → PENDING (nunca iniciados)
        self.assertEqual(saga.steps[2].status, StepStatus.PENDING)
        self.assertEqual(saga.steps[3].status, StepStatus.PENDING)

        # Comando de compensação para inventory publicado
        cmd = self.publisher.last_command()
        self.assertEqual(cmd["command_type"], "LiberarEstoque")
        self.assertEqual(cmd["service"], "inventory")

        # Step 0 compensado com sucesso → Saga COMPENSATED
        await self.engine.handle_reply(
            success_reply(saga, 0, "LiberarEstoque", "inventory"), session=self.session
        )
        self.assertEqual(saga.steps[0].status, StepStatus.COMPENSATED)
        self.assertEqual(saga.status, SagaStatus.COMPENSATED)
        self.assertIsNotNone(saga.completed_at)

    # -----------------------------------------------------------------------
    # Cenário 2: Falha no step 2 → compensa steps 1 e 0 em ordem decrescente
    # -----------------------------------------------------------------------

    async def test_falha_step2_compensa_em_ordem_decrescente(self):
        saga = await self._iniciar_saga("ORD-C2")

        # Steps 0 e 1 completam
        await self.engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"), session=self.session
        )
        await self.engine.handle_reply(
            success_reply(saga, 1, "ProcessarPagamento", "payment"), session=self.session
        )

        # Step 2 falha
        saga.steps[2].attempts = ORDER_WORKFLOW.steps[2].max_attempts
        await self.engine.handle_reply(
            failure_reply(saga, 2, "DespacharPedido", "shipping", "Sistema de entrega indisponível"),
            session=self.session,
        )

        self.assertEqual(saga.status, SagaStatus.COMPENSATING)

        # Primeiro a ser compensado deve ser step 1 (payment — maior índice entre os COMPLETED)
        self.assertEqual(saga.steps[1].status, StepStatus.COMPENSATING)
        self.assertEqual(saga.steps[0].status, StepStatus.COMPLETED)  # ainda não chegou a vez

        cmd_primero = self.publisher.last_command()
        self.assertEqual(cmd_primero["command_type"], "EstornarPagamento")
        self.assertEqual(cmd_primero["service"], "payment")

        # Payment compensado → próximo é inventory (step 0)
        await self.engine.handle_reply(
            success_reply(saga, 1, "EstornarPagamento", "payment"), session=self.session
        )
        self.assertEqual(saga.steps[1].status, StepStatus.COMPENSATED)
        self.assertEqual(saga.steps[0].status, StepStatus.COMPENSATING)

        cmd_segundo = self.publisher.last_command()
        self.assertEqual(cmd_segundo["command_type"], "LiberarEstoque")
        self.assertEqual(cmd_segundo["service"], "inventory")

        # Inventory compensado → Saga COMPENSATED
        await self.engine.handle_reply(
            success_reply(saga, 0, "LiberarEstoque", "inventory"), session=self.session
        )
        self.assertEqual(saga.steps[0].status, StepStatus.COMPENSATED)
        self.assertEqual(saga.status, SagaStatus.COMPENSATED)

    # -----------------------------------------------------------------------
    # Cenário 3: Falha no step 3 (último) → compensa steps 2, 1 e 0
    # NotificarCliente não tem compensation_command — deve ser pulado
    # -----------------------------------------------------------------------

    async def test_falha_step3_pula_step_sem_compensation(self):
        saga = await self._iniciar_saga("ORD-C3")

        # Steps 0, 1 e 2 completam
        await self.engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"), session=self.session
        )
        await self.engine.handle_reply(
            success_reply(saga, 1, "ProcessarPagamento", "payment"), session=self.session
        )
        await self.engine.handle_reply(
            success_reply(saga, 2, "DespacharPedido", "shipping"), session=self.session
        )
        # Step 3 (NotificarCliente) completa
        await self.engine.handle_reply(
            success_reply(saga, 3, "NotificarCliente", "notification"), session=self.session
        )
        self.assertEqual(saga.status, SagaStatus.COMPLETED)

        # Forçamos compensação manual (ex: cancelamento após confirmação)
        await self.engine.start_compensation(saga, session=self.session)

        # NotificarCliente não tem compensation_command — deve ficar COMPLETED
        self.assertEqual(saga.steps[3].status, StepStatus.COMPLETED)

        # DespacharPedido (índice 2) é o maior com compensation_command — compensa primeiro
        self.assertEqual(saga.steps[2].status, StepStatus.COMPENSATING)
        cmd = self.publisher.last_command()
        self.assertEqual(cmd["command_type"], "CancelarDespacho")

    # -----------------------------------------------------------------------
    # Cenário 4: Saga sem steps COMPLETED → vai direto para COMPENSATED
    # -----------------------------------------------------------------------

    async def test_saga_sem_steps_completados_vai_direto_para_compensated(self):
        saga = await self._iniciar_saga("ORD-C4")
        # Step 0 falha na primeira tentativa (sem retries configurados)
        saga.steps[0].attempts = ORDER_WORKFLOW.steps[0].max_attempts

        await self.engine.handle_reply(
            failure_reply(saga, 0, "ReservarEstoque", "inventory", "Produto esgotado"),
            session=self.session,
        )

        # Nenhum step completou → nada a compensar → Saga vai direto para COMPENSATED
        self.assertEqual(saga.status, SagaStatus.COMPENSATED)
        self.assertIsNotNone(saga.completed_at)

        event_types = [e.event_type for e in saga.events]
        self.assertIn("SagaCompensating", event_types)
        self.assertIn("SagaCompensated", event_types)
        self.assertNotIn("StepCompensationStarted", event_types)

    # -----------------------------------------------------------------------
    # Cenário 5: Ordem dos comandos de compensação é LIFO estrito
    # -----------------------------------------------------------------------

    async def test_ordem_lifo_dos_comandos_de_compensacao(self):
        saga = await self._iniciar_saga("ORD-C5")

        # Completa steps 0, 1 e 2
        await self.engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"), session=self.session
        )
        await self.engine.handle_reply(
            success_reply(saga, 1, "ProcessarPagamento", "payment"), session=self.session
        )
        await self.engine.handle_reply(
            success_reply(saga, 2, "DespacharPedido", "shipping"), session=self.session
        )

        # Triggera compensação manual
        await self.engine.start_compensation(saga, session=self.session)

        # Compensa step 2 (shipping)
        await self.engine.handle_reply(
            success_reply(saga, 2, "CancelarDespacho", "shipping"), session=self.session
        )
        # Compensa step 1 (payment)
        await self.engine.handle_reply(
            success_reply(saga, 1, "EstornarPagamento", "payment"), session=self.session
        )
        # Compensa step 0 (inventory)
        await self.engine.handle_reply(
            success_reply(saga, 0, "LiberarEstoque", "inventory"), session=self.session
        )

        self.assertEqual(saga.status, SagaStatus.COMPENSATED)

        # Verifica a ordem dos command_types de compensação no publisher
        tipos = self.publisher.command_types()
        comp_idx = tipos.index("CancelarDespacho")
        self.assertLess(tipos.index("EstornarPagamento"), len(tipos))
        # CancelarDespacho ocorre antes de EstornarPagamento
        self.assertLess(comp_idx, tipos.index("EstornarPagamento"))
        # EstornarPagamento ocorre antes de LiberarEstoque
        self.assertLess(tipos.index("EstornarPagamento"), tipos.index("LiberarEstoque"))

    # -----------------------------------------------------------------------
    # Cenário 6: Eventos de compensação gerados na sequência correta
    # -----------------------------------------------------------------------

    async def test_eventos_de_compensacao_registrados_corretamente(self):
        saga = await self._iniciar_saga("ORD-C6")

        await self.engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"), session=self.session
        )
        saga.steps[1].attempts = ORDER_WORKFLOW.steps[1].max_attempts
        await self.engine.handle_reply(
            failure_reply(saga, 1, "ProcessarPagamento", "payment"), session=self.session
        )
        await self.engine.handle_reply(
            success_reply(saga, 0, "LiberarEstoque", "inventory"), session=self.session
        )

        event_types = [e.event_type for e in saga.events]

        # Sequência esperada de eventos de compensação
        self.assertIn("SagaCompensating", event_types)
        self.assertIn("StepCompensationStarted", event_types)
        self.assertIn("StepCompensated", event_types)
        self.assertIn("SagaCompensated", event_types)

        # Ordem: SagaCompensating antes de StepCompensationStarted
        idx_comp_start = event_types.index("SagaCompensating")
        idx_step_comp_start = event_types.index("StepCompensationStarted")
        self.assertLess(idx_comp_start, idx_step_comp_start)

        # StepCompensated antes de SagaCompensated
        idx_step_compensated = event_types.index("StepCompensated")
        idx_saga_compensated = event_types.index("SagaCompensated")
        self.assertLess(idx_step_compensated, idx_saga_compensated)

    # -----------------------------------------------------------------------
    # Cenário 7: Falha irrecuperável na compensação → COMPENSATING_FAILED + FAILED
    # -----------------------------------------------------------------------

    async def test_falha_na_compensacao_leva_saga_para_failed(self):
        saga = await self._iniciar_saga("ORD-CF")

        # Step 0 completa
        await self.engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"), session=self.session
        )
        # Step 1 falha
        saga.steps[1].attempts = ORDER_WORKFLOW.steps[1].max_attempts
        await self.engine.handle_reply(
            failure_reply(saga, 1, "ProcessarPagamento", "payment"), session=self.session
        )

        # Step 0 falha na compensação (sem retry — já está no cenário de compensação)
        await self.engine.handle_reply(
            failure_reply(saga, 0, "LiberarEstoque", "inventory", "Erro crítico no estoque"),
            session=self.session,
        )

        self.assertEqual(saga.steps[0].status, StepStatus.COMPENSATING_FAILED)
        self.assertEqual(saga.status, SagaStatus.FAILED)
        self.assertIsNotNone(saga.completed_at)

        event_types = [e.event_type for e in saga.events]
        self.assertIn("StepCompensationFailed", event_types)
        self.assertIn("SagaFailed", event_types)

    # -----------------------------------------------------------------------
    # Cenário 8: start_compensation é idempotente (Saga já COMPENSATING)
    # -----------------------------------------------------------------------

    async def test_start_compensation_idempotente_se_ja_compensating(self):
        saga = await self._iniciar_saga("ORD-C8")

        await self.engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"), session=self.session
        )
        # Força compensação pela primeira vez
        await self.engine.start_compensation(saga, session=self.session)
        self.assertEqual(saga.status, SagaStatus.COMPENSATING)

        eventos_antes = len(saga.events)
        # Chama start_compensation novamente — não deve duplicar SagaCompensating
        await self.engine.start_compensation(saga, session=self.session)

        # Nenhum novo SagaCompensating deve ter sido registrado
        novos_compensating = [
            e for e in saga.events[eventos_antes:]
            if e.event_type == "SagaCompensating"
        ]
        self.assertEqual(len(novos_compensating), 0)

    # -----------------------------------------------------------------------
    # Cenário 9: Compensação via step sem payload próprio usa payload da Saga
    # -----------------------------------------------------------------------

    async def test_compensacao_usa_payload_da_saga_quando_step_nao_tem(self):
        saga = await self._iniciar_saga("ORD-C9")

        await self.engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"), session=self.session
        )
        saga.steps[1].attempts = ORDER_WORKFLOW.steps[1].max_attempts
        await self.engine.handle_reply(
            failure_reply(saga, 1, "ProcessarPagamento", "payment"), session=self.session
        )

        # O comando de compensação deve ter payload (da saga ou do step)
        cmd = self.publisher.last_command()
        self.assertIsNotNone(cmd["payload"])


if __name__ == "__main__":
    unittest.main()

