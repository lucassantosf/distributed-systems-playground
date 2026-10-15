"""
Testes unitários para SagaEngine (engine.py) — Card 2.4.

Cobre:
  - start_saga: inicialização, transição para RUNNING, despacho de step 0 e eventos
  - start_saga: idempotência por order_id
  - handle_reply: avanço no happy path até Saga COMPLETED
  - handle_reply: falha em step intermediário disparando compensação reversa
  - handle_reply: falha na compensação levando Saga para FAILED
  - handle_reply: proteção contra reply duplicada / tardia (idempotência)
  - start_compensation: rollback em ordem decrescente de step_index
  - handle_timeout: expiração de step em RUNNING disparando rollback
  - handle_timeout: ignorado quando step já concluiu
"""
import asyncio
import os
import sys
import unittest
from datetime import datetime, timezone

# Permite importar orchestrator sem instalação
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))

from app.core.enums import SagaStatus, StepStatus
from app.core.engine import SagaEngine
from app.core.workflow import ORDER_WORKFLOW, StepDefinition, WorkflowDefinition
from app.models.saga import Saga, SagaStep, SagaEvent


class MockSession:
    """
    Sessão em memória para testes unitários isolados (sem banco de dados).
    """
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
    """
    Gravador de comandos despachados pelo Engine.
    """
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


class TestSagaEngine(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.session = MockSession()
        self.publisher = MockPublisher()
        self.engine = SagaEngine(
            session_factory=None,
            workflow=ORDER_WORKFLOW,
            publisher=self.publisher,
        )

    # -----------------------------------------------------------------------
    # start_saga
    # -----------------------------------------------------------------------

    async def test_start_saga_inicializa_corretamente(self):
        payload = {"order_id": "ORD-1", "total_amount": 150.0}
        saga = await self.engine.start_saga("ORD-1", payload, session=self.session)

        # Saga em RUNNING
        self.assertEqual(saga.status, SagaStatus.RUNNING)
        self.assertEqual(saga.order_id, "ORD-1")
        self.assertEqual(saga.current_step_index, 0)
        self.assertEqual(len(saga.steps), 4)

        # Step 0 está RUNNING
        step_0 = saga.steps[0]
        self.assertEqual(step_0.status, StepStatus.RUNNING)
        self.assertEqual(step_0.step_name, "ReservarEstoque")
        self.assertEqual(step_0.attempts, 1)
        self.assertIsNotNone(step_0.command_id)

        # Steps 1 a 3 estão PENDING
        for s in saga.steps[1:]:
            self.assertEqual(s.status, StepStatus.PENDING)

        # Eventos gravados
        event_types = [e.event_type for e in saga.events]
        self.assertIn("SagaStarted", event_types)
        self.assertIn("StepStarted", event_types)

        # Comando despachado no publisher
        self.assertEqual(len(self.publisher.commands), 1)
        cmd = self.publisher.commands[0]
        self.assertEqual(cmd["service"], "inventory")
        self.assertEqual(cmd["command_type"], "ReservarEstoque")
        self.assertEqual(cmd["command_id"], step_0.command_id)

    async def test_start_saga_idempotencia_order_id(self):
        payload = {"order_id": "ORD-DUP", "total_amount": 100.0}
        saga1 = await self.engine.start_saga("ORD-DUP", payload, session=self.session)
        saga2 = await self.engine.start_saga("ORD-DUP", payload, session=self.session)

        self.assertEqual(saga1.id, saga2.id)
        # Não publica comando duplicado
        self.assertEqual(len(self.publisher.commands), 1)

    # -----------------------------------------------------------------------
    # handle_reply — Happy Path
    # -----------------------------------------------------------------------

    async def test_happy_path_completo_ate_completed(self):
        payload = {"order_id": "ORD-HAPPY", "total_amount": 250.0}
        saga = await self.engine.start_saga("ORD-HAPPY", payload, session=self.session)

        # Step 0 (inventory) responde sucesso
        reply_0 = {
            "saga_id": str(saga.id),
            "command_id": saga.steps[0].command_id,
            "command_type": "ReservarEstoque",
            "service": "inventory",
            "success": True,
            "payload": {"reserved": True},
        }
        await self.engine.handle_reply(reply_0, session=self.session)
        self.assertEqual(saga.steps[0].status, StepStatus.COMPLETED)
        self.assertEqual(saga.steps[1].status, StepStatus.RUNNING)
        self.assertEqual(saga.current_step_index, 1)

        # Step 1 (payment) responde sucesso
        reply_1 = {
            "saga_id": str(saga.id),
            "command_id": saga.steps[1].command_id,
            "command_type": "ProcessarPagamento",
            "service": "payment",
            "success": True,
            "payload": {"payment_id": "PAY-1"},
        }
        await self.engine.handle_reply(reply_1, session=self.session)
        self.assertEqual(saga.steps[1].status, StepStatus.COMPLETED)
        self.assertEqual(saga.steps[2].status, StepStatus.RUNNING)
        self.assertEqual(saga.current_step_index, 2)

        # Step 2 (shipping) responde sucesso
        reply_2 = {
            "saga_id": str(saga.id),
            "command_id": saga.steps[2].command_id,
            "command_type": "DespacharPedido",
            "service": "shipping",
            "success": True,
            "payload": {"tracking_code": "TRACK-1"},
        }
        await self.engine.handle_reply(reply_2, session=self.session)
        self.assertEqual(saga.steps[2].status, StepStatus.COMPLETED)
        self.assertEqual(saga.steps[3].status, StepStatus.RUNNING)
        self.assertEqual(saga.current_step_index, 3)

        # Step 3 (notification) responde sucesso (último step)
        reply_3 = {
            "saga_id": str(saga.id),
            "command_id": saga.steps[3].command_id,
            "command_type": "NotificarCliente",
            "service": "notification",
            "success": True,
            "payload": {"sent": True},
        }
        await self.engine.handle_reply(reply_3, session=self.session)
        self.assertEqual(saga.steps[3].status, StepStatus.COMPLETED)

        # Saga finalizada com sucesso
        self.assertEqual(saga.status, SagaStatus.COMPLETED)
        self.assertIsNotNone(saga.completed_at)

        event_types = [e.event_type for e in saga.events]
        self.assertIn("SagaCompleted", event_types)

    # -----------------------------------------------------------------------
    # handle_reply — Falha com Rollback / Compensação
    # -----------------------------------------------------------------------

    async def test_falha_no_pagamento_dispara_compensacao_do_estoque(self):
        payload = {"order_id": "ORD-COMP", "total_amount": 12000.0}
        saga = await self.engine.start_saga("ORD-COMP", payload, session=self.session)

        # Step 0 (estoque) conclui com sucesso
        reply_0 = {
            "saga_id": str(saga.id),
            "command_id": saga.steps[0].command_id,
            "command_type": "ReservarEstoque",
            "service": "inventory",
            "success": True,
        }
        await self.engine.handle_reply(reply_0, session=self.session)
        self.assertEqual(saga.steps[0].status, StepStatus.COMPLETED)

        # Step 1 (pagamento) falha
        # Simulamos tentativas já no limite para ir direto para FAILED
        saga.steps[1].attempts = 3
        reply_1 = {
            "saga_id": str(saga.id),
            "command_id": saga.steps[1].command_id,
            "command_type": "ProcessarPagamento",
            "service": "payment",
            "success": False,
            "error_message": "Limite de crédito excedido",
        }
        await self.engine.handle_reply(reply_1, session=self.session)

        # Step 1 fica FAILED
        self.assertEqual(saga.steps[1].status, StepStatus.FAILED)
        # Saga entrou em COMPENSATING
        self.assertEqual(saga.status, SagaStatus.COMPENSATING)
        # Step 0 entrou em COMPENSATING
        self.assertEqual(saga.steps[0].status, StepStatus.COMPENSATING)

        # Verifica comando de compensação despachado para o estoque
        comp_cmd = self.publisher.commands[-1]
        self.assertEqual(comp_cmd["service"], "inventory")
        self.assertEqual(comp_cmd["command_type"], "LiberarEstoque")

        # Worker do estoque responde sucesso na compensação
        comp_reply = {
            "saga_id": str(saga.id),
            "command_id": saga.steps[0].command_id,
            "command_type": "LiberarEstoque",
            "service": "inventory",
            "success": True,
        }
        await self.engine.handle_reply(comp_reply, session=self.session)

        # Step 0 fica COMPENSATED e Saga fica COMPENSATED
        self.assertEqual(saga.steps[0].status, StepStatus.COMPENSATED)
        self.assertEqual(saga.status, SagaStatus.COMPENSATED)

        event_types = [e.event_type for e in saga.events]
        self.assertIn("StepCompensationStarted", event_types)
        self.assertIn("StepCompensated", event_types)
        self.assertIn("SagaCompensated", event_types)

    async def test_falha_na_compensacao_transiciona_saga_para_failed(self):
        payload = {"order_id": "ORD-COMP-FAIL"}
        saga = await self.engine.start_saga("ORD-COMP-FAIL", payload, session=self.session)

        # Step 0 completa
        await self.engine.handle_reply({
            "saga_id": str(saga.id),
            "command_id": saga.steps[0].command_id,
            "command_type": "ReservarEstoque",
            "service": "inventory",
            "success": True,
        }, session=self.session)

        # Step 1 falha imediatamente
        saga.steps[1].attempts = 3
        await self.engine.handle_reply({
            "saga_id": str(saga.id),
            "command_id": saga.steps[1].command_id,
            "command_type": "ProcessarPagamento",
            "service": "payment",
            "success": False,
            "error_message": "Erro fatal",
        }, session=self.session)

        # Worker falha na compensação do Step 0
        await self.engine.handle_reply({
            "saga_id": str(saga.id),
            "command_id": saga.steps[0].command_id,
            "command_type": "LiberarEstoque",
            "service": "inventory",
            "success": False,
            "error_message": "Falha na desfeita do estoque",
        }, session=self.session)

        self.assertEqual(saga.steps[0].status, StepStatus.COMPENSATING_FAILED)
        self.assertEqual(saga.status, SagaStatus.FAILED)

        event_types = [e.event_type for e in saga.events]
        self.assertIn("StepCompensationFailed", event_types)
        self.assertIn("SagaFailed", event_types)

    # -----------------------------------------------------------------------
    # Idempotência de Replies
    # -----------------------------------------------------------------------

    async def test_reply_duplicada_ignorada(self):
        payload = {"order_id": "ORD-IDEMP"}
        saga = await self.engine.start_saga("ORD-IDEMP", payload, session=self.session)

        step_0_cmd_id = saga.steps[0].command_id
        reply = {
            "saga_id": str(saga.id),
            "command_id": step_0_cmd_id,
            "command_type": "ReservarEstoque",
            "service": "inventory",
            "success": True,
        }

        # Primeira reply processa com sucesso
        await self.engine.handle_reply(reply, session=self.session)
        self.assertEqual(saga.steps[0].status, StepStatus.COMPLETED)
        initial_events_count = len(saga.events)

        # Segunda reply com mesmo command_id deve ser ignorada
        await self.engine.handle_reply(reply, session=self.session)
        self.assertEqual(saga.steps[0].status, StepStatus.COMPLETED)
        # Nenhum evento extra adicionado
        self.assertEqual(len(saga.events), initial_events_count)

    # -----------------------------------------------------------------------
    # handle_timeout
    # -----------------------------------------------------------------------

    async def test_handle_timeout_dispara_compensacao(self):
        payload = {"order_id": "ORD-TIMEOUT"}
        saga = await self.engine.start_saga("ORD-TIMEOUT", payload, session=self.session)

        # Step 0 está RUNNING e expira o timeout
        await self.engine.handle_timeout(str(saga.id), step_index=0, session=self.session)

        self.assertEqual(saga.steps[0].status, StepStatus.FAILED)
        self.assertIn("Timeout", saga.steps[0].error_message)
        # Como o Step 0 falhou e nenhum step anterior completou, saga transiciona para COMPENSATED
        self.assertEqual(saga.status, SagaStatus.COMPENSATED)

        event_types = [e.event_type for e in saga.events]
        self.assertIn("StepTimeout", event_types)
        self.assertIn("StepFailed", event_types)

    async def test_handle_timeout_ignorado_se_step_ja_completou(self):
        payload = {"order_id": "ORD-TIMEOUT-OK"}
        saga = await self.engine.start_saga("ORD-TIMEOUT-OK", payload, session=self.session)

        # Step 0 conclui a tempo
        await self.engine.handle_reply({
            "saga_id": str(saga.id),
            "command_id": saga.steps[0].command_id,
            "command_type": "ReservarEstoque",
            "service": "inventory",
            "success": True,
        }, session=self.session)
        self.assertEqual(saga.steps[0].status, StepStatus.COMPLETED)

        # Timeout tardio para step 0 chega após conclusão
        await self.engine.handle_timeout(str(saga.id), step_index=0, session=self.session)
        # Status deve permanecer COMPLETED, não FAILED
        self.assertEqual(saga.steps[0].status, StepStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()

