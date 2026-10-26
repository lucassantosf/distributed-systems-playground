"""
Testes unitários para Card 5.2 — Timeout Configurável por Step.

Cobre:
  - _arm_timeout cria asyncio.Task no mapa _timeout_tasks
  - _cancel_timeout remove a task e a cancela antes de disparar
  - handle_reply cancela o watchdog quando a reply chega a tempo
  - handle_reply arma watchdog para o próximo step após avançar
  - Watchdog dispara handle_timeout quando timeout_seconds esgota sem reply
  - Watchdog é cancelado se o step completar antes do timer expirar
  - handle_timeout ignora step já concluído (guard de idempotência)
  - Timeout no step 0 → Saga vai direto para COMPENSATED (nada a compensar)
  - Timeout em step intermediário → compensação em ordem reversa
  - _arm_timeout desabilitado quando timeout_seconds <= 0
  - evento StepTimeout contém timeout_seconds correto
"""
import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))

from app.core.enums import SagaStatus, StepStatus
from app.core.engine import SagaEngine
from app.core.workflow import ORDER_WORKFLOW, WorkflowDefinition, StepDefinition
from app.models.saga import Saga, SagaStep, SagaEvent


# ---------------------------------------------------------------------------
# Helpers de teste
# ---------------------------------------------------------------------------

class MockSession:
    """Sessão em memória para testes isolados."""
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

    def begin(self):
        return _NullContextManager()


class MockSessionFactory:
    """
    Context manager que simula AsyncSessionLocal para o watchdog de timeout.
    Permite que handle_timeout (sem session explícita) use a mesma MockSession
    dos testes em vez de tentar abrir conexão real com o banco.
    """
    def __init__(self, session: MockSession):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        pass

    def begin(self):
        return _NullContextManager()


class _NullContextManager:
    """Context manager nulo para simular session.begin()."""
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockPublisher:
    """Gravador de comandos despachados pelo Engine."""
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


# ---------------------------------------------------------------------------
# Workflow com timeout muito curto para testes automatizados
# ---------------------------------------------------------------------------

TIMEOUT_CURTO = WorkflowDefinition(
    name="TesteTimeout",
    steps=[
        StepDefinition(
            name="ReservarEstoque",
            service="inventory",
            command_type="ReservarEstoque",
            compensation_command="LiberarEstoque",
            timeout_seconds=0.05,   # 50ms — expira rapidamente no teste
            max_attempts=3,
        ),
        StepDefinition(
            name="ProcessarPagamento",
            service="payment",
            command_type="ProcessarPagamento",
            compensation_command="EstornarPagamento",
            timeout_seconds=0.05,
            max_attempts=3,
        ),
        StepDefinition(
            name="DespacharPedido",
            service="shipping",
            command_type="DespacharPedido",
            compensation_command="CancelarDespacho",
            timeout_seconds=0.05,
            max_attempts=3,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Testes unitários de _arm_timeout e _cancel_timeout
# ---------------------------------------------------------------------------

class TestArmCancelTimeout(unittest.IsolatedAsyncioTestCase):
    """Testes das primitivas _arm_timeout e _cancel_timeout isoladas."""

    async def asyncSetUp(self):
        self.session = MockSession()
        self.engine = SagaEngine(
            session_factory=None,
            workflow=TIMEOUT_CURTO,
            publisher=None,
        )

    async def test_arm_timeout_registra_task_no_mapa(self):
        """_arm_timeout deve inserir uma Task no dicionário _timeout_tasks."""
        self.assertEqual(len(self.engine._timeout_tasks), 0)

        self.engine._arm_timeout(
            saga_id="saga-1",
            step_index=0,
            command_id="cmd-1",
            timeout_seconds=10.0,
        )

        self.assertIn("cmd-1", self.engine._timeout_tasks)
        task = self.engine._timeout_tasks["cmd-1"]
        self.assertIsInstance(task, asyncio.Task)

        # Cancela para não gerar warnings de tasks pendentes
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    async def test_arm_timeout_desabilitado_quando_zero(self):
        """_arm_timeout com timeout_seconds=0 não deve criar nenhuma task."""
        self.engine._arm_timeout(
            saga_id="saga-2",
            step_index=0,
            command_id="cmd-2",
            timeout_seconds=0,
        )
        self.assertNotIn("cmd-2", self.engine._timeout_tasks)

    async def test_arm_timeout_desabilitado_quando_negativo(self):
        """_arm_timeout com timeout_seconds negativo não deve criar nenhuma task."""
        self.engine._arm_timeout(
            saga_id="saga-neg",
            step_index=0,
            command_id="cmd-neg",
            timeout_seconds=-1,
        )
        self.assertNotIn("cmd-neg", self.engine._timeout_tasks)

    async def test_cancel_timeout_remove_task_e_cancela(self):
        """_cancel_timeout deve cancelar a task e removê-la do mapa."""
        self.engine._arm_timeout(
            saga_id="saga-3",
            step_index=0,
            command_id="cmd-3",
            timeout_seconds=60.0,
        )
        self.assertIn("cmd-3", self.engine._timeout_tasks)
        task = self.engine._timeout_tasks["cmd-3"]

        self.engine._cancel_timeout("cmd-3")

        # Task cancelada e removida do mapa
        self.assertNotIn("cmd-3", self.engine._timeout_tasks)
        # Aguarda um ciclo para propagar o cancelamento
        await asyncio.sleep(0)
        self.assertTrue(task.cancelled() or task.done())

    async def test_cancel_timeout_command_id_inexistente_nao_gera_erro(self):
        """_cancel_timeout com command_id desconhecido não deve lançar exceção."""
        # Não deve lançar KeyError nem outra exceção
        self.engine._cancel_timeout("cmd-inexistente")


# ---------------------------------------------------------------------------
# Testes de integração com handle_reply (sem watchdog real)
# ---------------------------------------------------------------------------

class TestTimeoutIntegracaoHandleReply(unittest.IsolatedAsyncioTestCase):
    """
    Testes que verificam que handle_reply corretamente cancela e arma watchdogs.
    Usa session_factory=None para manter os testes rápidos (sem watchdog real).
    """

    async def asyncSetUp(self):
        self.session = MockSession()
        self.publisher = MockPublisher()
        self.engine = SagaEngine(
            session_factory=None,
            workflow=TIMEOUT_CURTO,
            publisher=self.publisher,
        )

    async def _iniciar_saga(self, order_id: str) -> Saga:
        return await self.engine.start_saga(
            order_id, {"order_id": order_id}, session=self.session
        )

    async def test_start_saga_arma_watchdog_para_step_0(self):
        """
        start_saga deve armar o watchdog para o command_id do Step 0.
        """
        saga = await self._iniciar_saga("ORD-ARM-0")
        step_0 = saga.steps[0]

        self.assertIn(step_0.command_id, self.engine._timeout_tasks)

        # Limpa para não gerar warnings
        self.engine._cancel_timeout(step_0.command_id)

    async def test_handle_reply_cancela_watchdog_quando_reply_chega(self):
        """
        Quando uma reply de sucesso chega, o watchdog deve ser cancelado
        e removido do mapa _timeout_tasks.
        """
        saga = await self._iniciar_saga("ORD-CANCEL-WD")
        step_0 = saga.steps[0]
        cmd_id = step_0.command_id

        self.assertIn(cmd_id, self.engine._timeout_tasks)

        await self.engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"),
            session=self.session,
        )

        self.assertNotIn(cmd_id, self.engine._timeout_tasks)
        self.assertEqual(step_0.status, StepStatus.COMPLETED)

    async def test_handle_reply_arma_watchdog_para_proximo_step(self):
        """
        Após avançar para o step N+1, um novo watchdog deve ser armado
        para o command_id do step N+1.
        """
        saga = await self._iniciar_saga("ORD-NEXT-WD")

        await self.engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"),
            session=self.session,
        )

        step_1 = saga.steps[1]
        self.assertIn(step_1.command_id, self.engine._timeout_tasks)

        # Limpa
        self.engine._cancel_timeout(step_1.command_id)

    async def test_watchdog_antigo_nao_persiste_apos_reply(self):
        """
        O command_id do step anterior não deve permanecer no mapa
        depois que a reply é processada.
        """
        saga = await self._iniciar_saga("ORD-OLD-WD")
        cmd_id_step0 = saga.steps[0].command_id

        await self.engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"),
            session=self.session,
        )

        # command_id do step 0 deve ter saído do mapa
        self.assertNotIn(cmd_id_step0, self.engine._timeout_tasks)

        # Limpa o watchdog do step 1
        self.engine._cancel_timeout(saga.steps[1].command_id)


# ---------------------------------------------------------------------------
# Testes de watchdog disparando handle_timeout
# (requerem session_factory para o watchdog encontrar a saga)
# ---------------------------------------------------------------------------

class TestWatchdogDisparo(unittest.IsolatedAsyncioTestCase):
    """
    Testes onde o watchdog precisa efetivamente disparar handle_timeout.
    Usa MockSessionFactory para que o watchdog (sem session) encontre as sagas.
    """

    async def asyncSetUp(self):
        self.session = MockSession()
        self.publisher = MockPublisher()
        self.session_factory = MockSessionFactory(self.session)

    def _make_engine(self) -> SagaEngine:
        return SagaEngine(
            session_factory=self.session_factory,
            workflow=TIMEOUT_CURTO,
            publisher=self.publisher,
        )

    async def _iniciar_saga(self, engine: SagaEngine, order_id: str) -> Saga:
        return await engine.start_saga(
            order_id, {"order_id": order_id}, session=self.session
        )

    async def test_watchdog_dispara_e_step_vai_para_failed(self):
        """
        Quando nenhuma reply chega em timeout_seconds, o watchdog deve
        chamar handle_timeout e transiticionar o step para FAILED.
        """
        engine = self._make_engine()
        saga = await self._iniciar_saga(engine, "ORD-WD-FIRE")
        step_0 = saga.steps[0]

        self.assertEqual(step_0.status, StepStatus.RUNNING)
        self.assertIn(step_0.command_id, engine._timeout_tasks)

        # Aguarda o timeout (50ms) + margem
        await asyncio.sleep(0.15)

        self.assertEqual(step_0.status, StepStatus.FAILED)
        self.assertIn("Timeout", step_0.error_message)

        event_types = [e.event_type for e in saga.events]
        self.assertIn("StepTimeout", event_types)
        self.assertIn("StepFailed", event_types)

    async def test_watchdog_dispara_e_saga_sem_compensacao_vai_para_compensated(self):
        """
        Timeout no Step 0 (sem steps anteriores completados) → Saga vai
        diretamente para COMPENSATED sem nenhum step de rollback.
        """
        engine = self._make_engine()
        saga = await self._iniciar_saga(engine, "ORD-WD-NO-COMP")

        await asyncio.sleep(0.15)

        self.assertEqual(saga.steps[0].status, StepStatus.FAILED)
        self.assertEqual(saga.status, SagaStatus.COMPENSATED)

        event_types = [e.event_type for e in saga.events]
        self.assertIn("SagaCompensated", event_types)

    async def test_watchdog_cancelado_se_reply_chega_antes(self):
        """
        Se a reply chega antes do timeout, o watchdog é cancelado
        e o step permanece COMPLETED — nunca FAILED.
        """
        engine = self._make_engine()
        saga = await self._iniciar_saga(engine, "ORD-WD-CANCEL")
        step_0 = saga.steps[0]

        # Reply chega antes do timeout
        await engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"),
            session=self.session,
        )
        self.assertEqual(step_0.status, StepStatus.COMPLETED)

        # Cancela o watchdog do step 1 (armado após a reply do step 0)
        # para não interferir na verificação do step 0
        if saga.steps[1].command_id:
            engine._cancel_timeout(saga.steps[1].command_id)

        # Aguarda para garantir que o watchdog cancelado do step 0 não altere nada
        await asyncio.sleep(0.15)

        self.assertEqual(step_0.status, StepStatus.COMPLETED)
        self.assertNotIn(step_0.command_id, engine._timeout_tasks)

    async def test_timeout_em_step_intermediario_inicia_compensacao_reversa(self):
        """
        Timeout no step 2, com steps 0 e 1 concluídos, deve iniciar
        compensação em ordem reversa (step 1 antes do step 0).
        """
        engine = self._make_engine()
        saga = await self._iniciar_saga(engine, "ORD-TIMEOUT-MID")

        # Steps 0 e 1 completam com reply manual
        await engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"),
            session=self.session,
        )
        await engine.handle_reply(
            success_reply(saga, 1, "ProcessarPagamento", "payment"),
            session=self.session,
        )

        step_2 = saga.steps[2]
        self.assertEqual(step_2.status, StepStatus.RUNNING)
        self.assertIn(step_2.command_id, engine._timeout_tasks)

        # Aguarda timeout do step 2
        await asyncio.sleep(0.15)

        self.assertEqual(step_2.status, StepStatus.FAILED)
        self.assertEqual(saga.status, SagaStatus.COMPENSATING)

        # Step 1 deve estar COMPENSATING (maior índice com compensation_command)
        self.assertEqual(saga.steps[1].status, StepStatus.COMPENSATING)
        self.assertEqual(saga.steps[0].status, StepStatus.COMPLETED)

        event_types = [e.event_type for e in saga.events]
        self.assertIn("StepTimeout", event_types)
        self.assertIn("SagaCompensating", event_types)
        self.assertIn("StepCompensationStarted", event_types)

        # Limpa watchdog do step 1
        engine._cancel_timeout(saga.steps[1].command_id)


# ---------------------------------------------------------------------------
# Testes de handle_timeout isolado (chamado diretamente, sem watchdog)
# ---------------------------------------------------------------------------

class TestHandleTimeoutDireto(unittest.IsolatedAsyncioTestCase):
    """
    Testes de handle_timeout chamado diretamente, sem depender do watchdog.
    """

    async def asyncSetUp(self):
        self.session = MockSession()
        self.publisher = MockPublisher()
        self.engine = SagaEngine(
            session_factory=None,
            workflow=TIMEOUT_CURTO,
            publisher=self.publisher,
        )

    async def _iniciar_saga(self, order_id: str) -> Saga:
        return await self.engine.start_saga(
            order_id, {"order_id": order_id}, session=self.session
        )

    async def test_handle_timeout_direto_transiciona_step_para_failed(self):
        """
        handle_timeout em step RUNNING deve transiticioná-lo para FAILED
        e iniciar compensação (neste caso sem steps anteriores → COMPENSATED).
        """
        saga = await self._iniciar_saga("ORD-HT-DIRECT")

        self.assertEqual(saga.steps[0].status, StepStatus.RUNNING)

        await self.engine.handle_timeout(str(saga.id), step_index=0, session=self.session)

        self.assertEqual(saga.steps[0].status, StepStatus.FAILED)
        self.assertIn("Timeout", saga.steps[0].error_message)
        self.assertEqual(saga.status, SagaStatus.COMPENSATED)

    async def test_handle_timeout_ignorado_se_step_ja_completou(self):
        """
        handle_timeout chamado após o step ter completado deve ser ignorado
        (reply chegou a tempo): step permanece COMPLETED.
        """
        saga = await self._iniciar_saga("ORD-HT-IGNORE")

        # Completa step 0
        await self.engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"),
            session=self.session,
        )
        self.assertEqual(saga.steps[0].status, StepStatus.COMPLETED)

        # Timeout tardio
        await self.engine.handle_timeout(str(saga.id), step_index=0, session=self.session)

        self.assertEqual(saga.steps[0].status, StepStatus.COMPLETED)

        event_types = [e.event_type for e in saga.events]
        self.assertNotIn("StepTimeout", event_types)

        # Cancela watchdog do step 1
        self.engine._cancel_timeout(saga.steps[1].command_id)

    async def test_timeout_evento_contem_timeout_seconds_correto(self):
        """
        O evento StepTimeout deve conter o valor correto de timeout_seconds
        conforme definido no WorkflowDefinition.
        """
        saga = await self._iniciar_saga("ORD-HT-EVENT")

        await self.engine.handle_timeout(str(saga.id), step_index=0, session=self.session)

        timeout_events = [e for e in saga.events if e.event_type == "StepTimeout"]
        self.assertEqual(len(timeout_events), 1)

        payload = timeout_events[0].event_payload
        self.assertEqual(payload["step_index"], 0)
        self.assertEqual(payload["timeout_seconds"], 0.05)

    async def test_timeout_registra_stepfailed_com_reason_timeout(self):
        """
        O evento StepFailed gerado por timeout deve ter reason='TIMEOUT' no payload.
        """
        saga = await self._iniciar_saga("ORD-HT-REASON")

        await self.engine.handle_timeout(str(saga.id), step_index=0, session=self.session)

        failed_events = [e for e in saga.events if e.event_type == "StepFailed"]
        self.assertEqual(len(failed_events), 1)
        self.assertEqual(failed_events[0].event_payload.get("reason"), "TIMEOUT")


if __name__ == "__main__":
    unittest.main()
