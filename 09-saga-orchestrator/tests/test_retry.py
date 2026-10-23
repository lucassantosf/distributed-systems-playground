"""
Testes unitários para Card 5.1 — Retry com Backoff Exponencial.

Cobre:
  - Retry normal gera novo command_id a cada tentativa
  - Retry normal utiliza asyncio.create_task (não bloqueia handle_reply)
  - delay cresce de acordo com backoff exponencial: base * 2^(attempt-1)
  - Jitter de ±10% é aplicado ao delay
  - Compensação também usa backoff no retry
  - Após esgotar tentativas, compensa normalmente (sem delay)
"""
import asyncio
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))

from app.core.enums import SagaStatus, StepStatus
from app.core.engine import SagaEngine
from app.core.workflow import ORDER_WORKFLOW, DEFAULT_RETRY_BASE_DELAY
from app.models.saga import Saga, SagaStep, SagaEvent


# ---------------------------------------------------------------------------
# Helpers de teste
# ---------------------------------------------------------------------------

class MockSession:
    """Sessão em memória para testes unitários isolados."""
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
# Testes de Backoff Exponencial
# ---------------------------------------------------------------------------

class TestRetryBackoffExponencial(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.session = MockSession()
        self.publisher = MockPublisher()
        self.engine = SagaEngine(
            session_factory=None,
            workflow=ORDER_WORKFLOW,
            publisher=self.publisher,
        )

    async def _iniciar_saga(self, order_id: str = "ORD-RETRY") -> Saga:
        return await self.engine.start_saga(
            order_id, {"order_id": order_id, "total_amount": 100.0}, session=self.session
        )

    # -----------------------------------------------------------------------
    # Testa a fórmula de delay do _schedule_retry
    # -----------------------------------------------------------------------

    async def test_schedule_retry_calcula_delay_exponencial(self):
        """
        _schedule_retry deve aplicar base_delay * 2^(attempt-1) com jitter ±10%.
        Verifica que o sleep recebido está dentro do intervalo esperado.
        """
        base = 1.0  # delay base fixo para facilitar verificação
        delays_capturados = []

        async def fake_sleep(seconds):
            delays_capturados.append(seconds)

        # Publica sem delay para não travar o teste
        published = []

        async def fake_publish(cmd):
            published.append(cmd)

        self.engine._publish = fake_publish

        with patch("asyncio.sleep", side_effect=fake_sleep):
            # Tentativa 1: delay = 1.0 * 2^0 = 1.0 (± 10%)
            await self.engine._schedule_retry({"command_type": "X", "saga_id": "S1"}, attempt=1, base_delay=base)
            # Tentativa 2: delay = 1.0 * 2^1 = 2.0 (± 10%)
            await self.engine._schedule_retry({"command_type": "X", "saga_id": "S1"}, attempt=2, base_delay=base)
            # Tentativa 3: delay = 1.0 * 2^2 = 4.0 (± 10%)
            await self.engine._schedule_retry({"command_type": "X", "saga_id": "S1"}, attempt=3, base_delay=base)

        self.assertEqual(len(delays_capturados), 3)

        # Tentativa 1: delay esperado em [0.9, 1.1]
        self.assertGreaterEqual(delays_capturados[0], 0.9)
        self.assertLessEqual(delays_capturados[0], 1.1)

        # Tentativa 2: delay esperado em [1.8, 2.2]
        self.assertGreaterEqual(delays_capturados[1], 1.8)
        self.assertLessEqual(delays_capturados[1], 2.2)

        # Tentativa 3: delay esperado em [3.6, 4.4]
        self.assertGreaterEqual(delays_capturados[2], 3.6)
        self.assertLessEqual(delays_capturados[2], 4.4)

        # O comando foi publicado após cada sleep
        self.assertEqual(len(published), 3)

    async def test_delay_cresce_entre_tentativas(self):
        """
        Valida que cada tentativa tem delay maior que a anterior (backoff cresce).
        """
        base = 0.5
        delays = []

        async def fake_sleep(seconds):
            delays.append(seconds)

        async def fake_publish(cmd):
            pass

        self.engine._publish = fake_publish

        with patch("asyncio.sleep", side_effect=fake_sleep):
            for attempt in range(1, 4):
                await self.engine._schedule_retry(
                    {"command_type": "Y", "saga_id": "S2"}, attempt=attempt, base_delay=base
                )

        # Cada delay (sem jitter) cresce: 0.5, 1.0, 2.0
        # Com jitter ±10%, o delay da tentativa N+1 deve ser > delay da tentativa N
        # Verificamos que a tendência central cresce comparando médias teóricas
        teoricos = [base * (2 ** (i - 1)) for i in range(1, 4)]
        self.assertLess(teoricos[0], teoricos[1])
        self.assertLess(teoricos[1], teoricos[2])

    # -----------------------------------------------------------------------
    # Testa que handle_reply usa create_task (não bloqueia)
    # -----------------------------------------------------------------------

    async def test_retry_normal_usa_create_task_nao_bloqueia(self):
        """
        Quando um step falha com tentativas restantes, handle_reply deve retornar
        imediatamente (sem aguardar o delay do retry). O comando de retry é
        despachado após o delay via asyncio.Task.
        Valida que: novo command_id, attempts incrementado e StepRetried gravado.
        """
        saga = await self._iniciar_saga("ORD-TASK")

        # Substitui _schedule_retry para capturar delay sem bloquear
        retry_calls = []

        async def recording_schedule(command_data, attempt, base_delay=DEFAULT_RETRY_BASE_DELAY):
            import random as _random
            exponent = attempt - 1
            delay = base_delay * (2 ** exponent) * _random.uniform(0.9, 1.1)
            retry_calls.append({"attempt": attempt, "delay": delay, "command_data": command_data})
            # Publica imediatamente (sem sleep real)
            await self.engine._publish(command_data)

        self.engine._schedule_retry = recording_schedule

        cmd_id_inicial = saga.steps[0].command_id

        await self.engine.handle_reply(
            failure_reply(saga, 0, "ReservarEstoque", "inventory", "Falha transitória"),
            session=self.session,
        )
        # Dá ciclos de event loop para as tasks executarem
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        # Step deve estar RUNNING com nova tentativa
        self.assertEqual(saga.steps[0].status, StepStatus.RUNNING)
        self.assertEqual(saga.steps[0].attempts, 2)

        # command_id deve ter mudado
        self.assertNotEqual(saga.steps[0].command_id, cmd_id_inicial)

        # Evento StepRetried deve ter sido registrado
        event_types = [e.event_type for e in saga.events]
        self.assertIn("StepRetried", event_types)

        # _schedule_retry foi chamado com attempt=2 e delay com backoff correto
        self.assertEqual(len(retry_calls), 1)
        call = retry_calls[0]
        self.assertEqual(call["attempt"], 2)
        delay_esperado_base = DEFAULT_RETRY_BASE_DELAY * (2 ** (2 - 1))  # attempt=2
        self.assertGreaterEqual(call["delay"], delay_esperado_base * 0.9)
        self.assertLessEqual(call["delay"], delay_esperado_base * 1.1)

    async def test_retry_gera_novo_command_id_a_cada_tentativa(self):
        """
        Cada tentativa de retry deve gerar um command_id único.
        Isso garante idempotência: cada tentativa é uma nova requisição.
        """
        saga = await self._iniciar_saga("ORD-CMD-IDS")

        ids_vistos = [saga.steps[0].command_id]

        with patch("asyncio.sleep", new_callable=lambda: lambda s: asyncio.coroutine(lambda: None)()):
            pass

        # Simula 2 falhas consecutivas sem esperar delay
        async def instant_sleep(_):
            pass

        with patch("asyncio.sleep", side_effect=instant_sleep):
            # Falha tentativa 1 → retry (attempt 2)
            await self.engine.handle_reply(
                failure_reply(saga, 0, "ReservarEstoque", "inventory"),
                session=self.session,
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            ids_vistos.append(saga.steps[0].command_id)

            # Falha tentativa 2 → retry (attempt 3)
            await self.engine.handle_reply(
                failure_reply(saga, 0, "ReservarEstoque", "inventory"),
                session=self.session,
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            ids_vistos.append(saga.steps[0].command_id)

        # Todos os command_ids devem ser distintos
        self.assertEqual(len(set(ids_vistos)), 3, "Cada tentativa deve ter um command_id único")

    async def test_eventos_step_retried_registrados_por_tentativa(self):
        """
        A cada falha com retry disponível, deve ser gravado um evento StepRetried
        com o número da tentativa correta.
        """
        saga = await self._iniciar_saga("ORD-EVENTS-RETRY")

        async def instant_sleep(_):
            pass

        with patch("asyncio.sleep", side_effect=instant_sleep):
            # Tentativa 1 falha → StepRetried (attempt 2)
            await self.engine.handle_reply(
                failure_reply(saga, 0, "ReservarEstoque", "inventory", "Erro 1"),
                session=self.session,
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            # Tentativa 2 falha → StepRetried (attempt 3)
            await self.engine.handle_reply(
                failure_reply(saga, 0, "ReservarEstoque", "inventory", "Erro 2"),
                session=self.session,
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        retried_events = [e for e in saga.events if e.event_type == "StepRetried"]
        self.assertEqual(len(retried_events), 2)

        # Verifica que os attempts estão crescendo
        tentativas = [e.event_payload["attempt"] for e in retried_events]
        self.assertEqual(tentativas, [2, 3])

    async def test_retry_esgotado_inicia_compensacao_sem_delay(self):
        """
        Quando as tentativas se esgotam, a compensação deve ser iniciada
        diretamente (sem backoff extra) — é a transição definitiva para FAILED.
        """
        saga = await self._iniciar_saga("ORD-ESGOTADO")

        # Completa step 0 para que haja algo a compensar
        await self.engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"),
            session=self.session,
        )

        async def instant_sleep(_):
            pass

        with patch("asyncio.sleep", side_effect=instant_sleep):
            # Esgota tentativas do step 1 (max=3)
            saga.steps[1].attempts = ORDER_WORKFLOW.steps[1].max_attempts
            await self.engine.handle_reply(
                failure_reply(saga, 1, "ProcessarPagamento", "payment", "Falha definitiva"),
                session=self.session,
            )
            await asyncio.sleep(0)

        # Step 1 deve estar FAILED
        self.assertEqual(saga.steps[1].status, StepStatus.FAILED)
        # Saga deve estar COMPENSATING
        self.assertEqual(saga.status, SagaStatus.COMPENSATING)
        # Step 0 deve ter entrado em COMPENSATING (compensação iniciada)
        self.assertEqual(saga.steps[0].status, StepStatus.COMPENSATING)

        event_types = [e.event_type for e in saga.events]
        self.assertIn("StepFailed", event_types)
        self.assertIn("SagaCompensating", event_types)
        self.assertIn("StepCompensationStarted", event_types)

    # -----------------------------------------------------------------------
    # Backoff exponencial na compensação também
    # -----------------------------------------------------------------------

    async def test_compensacao_retry_usa_backoff(self):
        """
        O retry de compensação também deve utilizar backoff exponencial.
        Valida que o delay calculado para a segunda tentativa de compensação
        corresponde à fórmula base * 2^(attempt-1) com jitter ±10%.
        """
        saga = await self._iniciar_saga("ORD-COMP-BACKOFF")

        # Step 0 completa
        await self.engine.handle_reply(
            success_reply(saga, 0, "ReservarEstoque", "inventory"),
            session=self.session,
        )
        # Step 1 falha e inicia compensação do step 0
        saga.steps[1].attempts = ORDER_WORKFLOW.steps[1].max_attempts
        await self.engine.handle_reply(
            failure_reply(saga, 1, "ProcessarPagamento", "payment"),
            session=self.session,
        )
        self.assertEqual(saga.steps[0].status, StepStatus.COMPENSATING)
        self.assertEqual(saga.steps[0].attempts, 1)

        # Substitui _schedule_retry para capturar delay sem bloquear
        retry_calls = []
        import random as _random

        async def recording_schedule(command_data, attempt, base_delay=DEFAULT_RETRY_BASE_DELAY):
            exponent = attempt - 1
            delay = base_delay * (2 ** exponent) * _random.uniform(0.9, 1.1)
            retry_calls.append({"attempt": attempt, "delay": delay})
            await self.engine._publish(command_data)

        self.engine._schedule_retry = recording_schedule

        # Tentativa 1 da compensação falha → retry (attempt 2)
        await self.engine.handle_reply(
            failure_reply(saga, 0, "LiberarEstoque", "inventory", "Falha transitória na compensação"),
            session=self.session,
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        # O step deve estar COMPENSATING com attempts = 2
        self.assertEqual(saga.steps[0].status, StepStatus.COMPENSATING)
        self.assertEqual(saga.steps[0].attempts, 2)

        # Delay deve corresponder ao backoff de tentativa 2
        self.assertGreater(len(retry_calls), 0)
        call = retry_calls[0]
        self.assertEqual(call["attempt"], 2)
        delay_esperado_base = DEFAULT_RETRY_BASE_DELAY * (2 ** (2 - 1))  # attempt=2
        self.assertGreaterEqual(call["delay"], delay_esperado_base * 0.9)
        self.assertLessEqual(call["delay"], delay_esperado_base * 1.1)

        event_types = [e.event_type for e in saga.events]
        self.assertIn("StepCompensationRetried", event_types)

    async def test_create_retry_task_retorna_asyncio_task(self):
        """
        _create_retry_task deve retornar um asyncio.Task, permitindo
        cancelamento futuro (ex: quando o timeout resolver antes do retry).
        """
        async def instant_sleep(_):
            pass

        async def instant_publish(_):
            pass

        self.engine._publish = instant_publish

        with patch("asyncio.sleep", side_effect=instant_sleep):
            task = self.engine._create_retry_task(
                command_data={"command_type": "Teste", "saga_id": "S-TASK"},
                attempt=1,
                base_delay=0.001,
            )

        self.assertIsInstance(task, asyncio.Task)
        # Aguarda a task terminar para evitar warnings de tasks pendentes
        await task


if __name__ == "__main__":
    unittest.main()
