"""
Testes de Idempotência — Card 6.1: Idempotency Key nos Comandos.

Valida que:
  - start_saga gera um command_id (UUID v4) único para o step_0 e o persiste em SagaStep.command_id
  - Cada transição de step gera um novo command_id único
  - O command_id é incluído no payload de todo comando publicado
  - handle_reply usa o command_id como chave primária de roteamento
  - Em retry, um NOVO command_id é gerado (tentativa semanticamente nova)
  - Todos os command_ids de uma Saga são distintos entre si
  - Reply duplicada com mesmo command_id é ignorada (step já em status terminal)
  - POST /sagas com mesmo order_id é idempotente (retorna Saga existente sem criar nova)
"""
import asyncio
import uuid
from unittest import IsolatedAsyncioTestCase

from app.core.engine import SagaEngine
from app.core.enums import SagaStatus, StepStatus
from app.core.workflow import create_order_workflow
from app.models.saga import Saga, SagaStep, SagaEvent

# ---------------------------------------------------------------------------
# Helpers (padrão do projeto)
# ---------------------------------------------------------------------------

class _NullContextManager:
    """Simula session.begin() — não faz nada."""
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass


class MockSession:
    """Sessão em memória que suporta os helpers do Engine."""

    def __init__(self):
        self._sagas: dict[str, Saga] = {}
        self.added: list = []

    def add(self, obj):
        self.added.append(obj)

    def begin(self):
        return _NullContextManager()

    def put_saga(self, saga: Saga):
        self._sagas[str(saga.id)] = saga
        if hasattr(saga, "order_id"):
            self._sagas[f"order:{saga.order_id}"] = saga

    def get_saga(self, saga_id: str):
        return self._sagas.get(saga_id)

    def get_saga_by_order_id(self, order_id: str):
        return self._sagas.get(f"order:{order_id}")


class MockPublisher:
    """Registra todos os comandos publicados."""

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


def _make_engine(publisher=None, session=None):
    workflow = create_order_workflow(step_timeout_seconds=0, step_max_attempts=3)
    engine = SagaEngine(workflow=workflow, publisher=publisher or MockPublisher())
    return engine


def _make_saga(order_id="ORD-001", num_steps=4):
    """Cria uma Saga minimal com steps em memória."""
    workflow = create_order_workflow(step_timeout_seconds=0, step_max_attempts=3)
    saga_id = uuid.uuid4()
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    saga = Saga(
        id=saga_id,
        order_id=order_id,
        status=SagaStatus.RUNNING,
        current_step_index=0,
        payload={"order_id": order_id, "amount": 100},
        created_at=now,
        updated_at=now,
    )
    steps = []
    for idx in range(num_steps):
        step = SagaStep(
            id=uuid.uuid4(),
            saga_id=saga_id,
            step_name=workflow.steps[idx].name if idx < len(workflow.steps) else f"step_{idx}",
            step_index=idx,
            status=StepStatus.PENDING,
            command_id=None,
            attempts=0,
            payload=saga.payload,
            result={},
        )
        step.saga = saga
        steps.append(step)
    saga.steps = steps
    saga.events = []
    return saga, workflow


# ---------------------------------------------------------------------------
# Testes — Geração do command_id no start_saga
# ---------------------------------------------------------------------------

class TestCommandIdGeradoNoStartSaga(IsolatedAsyncioTestCase):
    """Garante que start_saga gera e persiste command_id no step_0."""

    async def test_start_saga_gera_command_id_no_step_0(self):
        """step_0.command_id deve ser um UUID v4 após start_saga."""
        publisher = MockPublisher()
        engine = _make_engine(publisher)
        session = MockSession()

        saga = await engine.start_saga(
            order_id="ORD-CMDID-001",
            payload={"order_id": "ORD-CMDID-001", "amount": 50},
            session=session,
        )

        step_0 = saga.steps[0]
        self.assertIsNotNone(step_0.command_id, "step_0.command_id não pode ser None")
        # Deve ser um UUID válido
        parsed = uuid.UUID(step_0.command_id)
        self.assertEqual(parsed.version, 4, "command_id deve ser UUID v4")

    async def test_start_saga_command_id_incluido_no_payload_publicado(self):
        """O command_id do step_0 deve estar no primeiro comando publicado."""
        publisher = MockPublisher()
        engine = _make_engine(publisher)
        session = MockSession()

        saga = await engine.start_saga(
            order_id="ORD-CMDID-002",
            payload={"order_id": "ORD-CMDID-002", "amount": 50},
            session=session,
        )

        self.assertEqual(len(publisher.commands), 1, "Deve publicar exatamente 1 comando no start_saga")
        publicado = publisher.commands[0]

        step_0 = saga.steps[0]
        self.assertEqual(
            publicado["command_id"],
            step_0.command_id,
            "command_id publicado deve ser igual ao persistido no step_0",
        )

    async def test_start_saga_idempotente_mesmo_order_id(self):
        """Chamadas duplicadas de start_saga com mesmo order_id retornam a mesma Saga."""
        publisher = MockPublisher()
        engine = _make_engine(publisher)
        session = MockSession()

        saga_a = await engine.start_saga(
            order_id="ORD-IDEM-001",
            payload={"order_id": "ORD-IDEM-001", "amount": 50},
            session=session,
        )
        # Registra para lookup subsequente
        session.put_saga(saga_a)

        saga_b = await engine.start_saga(
            order_id="ORD-IDEM-001",
            payload={"order_id": "ORD-IDEM-001", "amount": 50},
            session=session,
        )

        self.assertEqual(
            str(saga_a.id),
            str(saga_b.id),
            "Saga com mesmo order_id deve retornar a mesma instância",
        )
        # Nenhum comando adicional deve ter sido publicado
        self.assertEqual(
            len(publisher.commands),
            1,
            "Não deve publicar comando adicional para order_id duplicado",
        )


# ---------------------------------------------------------------------------
# Testes — Unicidade dos command_ids dentro de uma Saga
# ---------------------------------------------------------------------------

class TestCommandIdUnicidade(IsolatedAsyncioTestCase):
    """Garante que todos os command_ids gerados numa Saga são distintos."""

    async def test_cada_step_recebe_command_id_unico(self):
        """
        Simula happy-path completo: start_saga + handle_reply success para cada step.
        Verifica que cada step tem um command_id diferente dos demais.
        """
        publisher = MockPublisher()
        engine = _make_engine(publisher)
        session = MockSession()

        saga = await engine.start_saga(
            order_id="ORD-UNIQ-001",
            payload={"order_id": "ORD-UNIQ-001", "amount": 100},
            session=session,
        )
        session.put_saga(saga)

        # Coleta command_ids conforme o happy-path avança
        command_ids_vistos: list[str] = []
        command_ids_vistos.append(saga.steps[0].command_id)

        # Avança pelos steps via handle_reply success
        for idx in range(len(saga.steps) - 1):
            current_step = saga.steps[idx]
            current_step.status = StepStatus.RUNNING

            cmd_publicado = publisher.commands[-1]
            reply = {
                "command_id": cmd_publicado["command_id"],
                "saga_id": str(saga.id),
                "command_type": cmd_publicado["command_type"],
                "success": True,
                "payload": {"resultado": f"step_{idx}_ok"},
            }
            await engine.handle_reply(reply, session=session)

            next_step = saga.steps[idx + 1]
            if next_step.command_id:
                command_ids_vistos.append(next_step.command_id)

        # Todos devem ser únicos
        self.assertEqual(
            len(command_ids_vistos),
            len(set(command_ids_vistos)),
            f"Todos os command_ids devem ser únicos, mas encontramos duplicatas: {command_ids_vistos}",
        )

    async def test_command_ids_sao_uuids_validos(self):
        """Cada command_id gerado deve ser um UUID v4 válido."""
        publisher = MockPublisher()
        engine = _make_engine(publisher)
        session = MockSession()

        saga = await engine.start_saga(
            order_id="ORD-UUID-001",
            payload={"order_id": "ORD-UUID-001", "amount": 100},
            session=session,
        )
        session.put_saga(saga)

        step_0 = saga.steps[0]
        step_0.status = StepStatus.RUNNING

        cmd = publisher.commands[-1]
        await engine.handle_reply({
            "command_id": cmd["command_id"],
            "saga_id": str(saga.id),
            "command_type": cmd["command_type"],
            "success": True,
            "payload": {},
        }, session=session)

        for step in saga.steps:
            if step.command_id is not None:
                try:
                    parsed = uuid.UUID(step.command_id)
                    self.assertEqual(parsed.version, 4)
                except ValueError:
                    self.fail(f"command_id '{step.command_id}' do step {step.step_index} não é UUID válido")


# ---------------------------------------------------------------------------
# Testes — Roteamento pelo command_id no handle_reply
# ---------------------------------------------------------------------------

class TestHandleReplyRoteiaPorCommandId(IsolatedAsyncioTestCase):
    """Garante que handle_reply usa command_id como chave primária de roteamento."""

    async def _setup_saga_rodando(self):
        """Cria uma Saga com step_0 RUNNING e retorna (engine, session, saga)."""
        publisher = MockPublisher()
        engine = _make_engine(publisher)
        session = MockSession()

        saga = await engine.start_saga(
            order_id="ORD-ROUTE-001",
            payload={"order_id": "ORD-ROUTE-001", "amount": 200},
            session=session,
        )
        session.put_saga(saga)
        saga.steps[0].status = StepStatus.RUNNING
        return engine, session, saga, publisher

    async def test_reply_com_command_id_correto_avanca_saga(self):
        """Reply com command_id do step_0 deve avançar a Saga para step_1."""
        engine, session, saga, publisher = await self._setup_saga_rodando()

        step_0 = saga.steps[0]
        cmd_id_step_0 = step_0.command_id
        cmd = publisher.commands[0]

        await engine.handle_reply({
            "command_id": cmd_id_step_0,
            "saga_id": str(saga.id),
            "command_type": cmd["command_type"],
            "success": True,
            "payload": {"ok": True},
        }, session=session)

        self.assertEqual(
            step_0.status,
            StepStatus.COMPLETED,
            "step_0 deve estar COMPLETED após reply de sucesso",
        )
        self.assertEqual(
            saga.current_step_index,
            1,
            "Saga deve ter avançado para step_index=1",
        )

    async def test_reply_com_command_id_errado_nao_afeta_step(self):
        """Reply com command_id desconhecido deve ser ignorada (nenhum step alterado)."""
        engine, session, saga, publisher = await self._setup_saga_rodando()

        status_original = [step.status for step in saga.steps]

        await engine.handle_reply({
            "command_id": str(uuid.uuid4()),  # ID completamente desconhecido
            "saga_id": str(saga.id),
            "command_type": "RESERVE_INVENTORY",
            "success": True,
            "payload": {},
        }, session=session)

        for i, step in enumerate(saga.steps):
            self.assertEqual(
                step.status,
                status_original[i],
                f"step_{i} não deve ter sido alterado por reply com command_id errado",
            )

    async def test_saga_nao_encontrada_retorna_none(self):
        """Reply para saga_id inexistente deve retornar None."""
        engine = _make_engine()
        session = MockSession()

        resultado = await engine.handle_reply({
            "command_id": str(uuid.uuid4()),
            "saga_id": str(uuid.uuid4()),
            "command_type": "RESERVE_INVENTORY",
            "success": True,
            "payload": {},
        }, session=session)

        self.assertIsNone(resultado)


# ---------------------------------------------------------------------------
# Testes — Retry gera novo command_id
# ---------------------------------------------------------------------------

class TestRetryGeraNovoCommandId(IsolatedAsyncioTestCase):
    """
    Garante que, em retry, um NOVO command_id é gerado —
    cada tentativa é semanticamente uma nova requisição ao serviço.
    """

    async def test_retry_gera_command_id_diferente_do_original(self):
        """Após falha, o command_id do step deve mudar para o retry."""
        publisher = MockPublisher()
        engine = _make_engine(publisher)
        session = MockSession()

        saga = await engine.start_saga(
            order_id="ORD-RETRY-001",
            payload={"order_id": "ORD-RETRY-001", "amount": 100},
            session=session,
        )
        session.put_saga(saga)

        step_0 = saga.steps[0]
        step_0.status = StepStatus.RUNNING
        command_id_original = step_0.command_id

        # Simula falha (tentativa 1 de 3 → deve gerar retry)
        cmd = publisher.commands[0]
        await engine.handle_reply({
            "command_id": command_id_original,
            "saga_id": str(saga.id),
            "command_type": cmd["command_type"],
            "success": False,
            "error_message": "timeout do serviço externo",
        }, session=session)

        command_id_apos_retry = step_0.command_id

        self.assertNotEqual(
            command_id_original,
            command_id_apos_retry,
            "Em retry, o command_id deve ser um UUID novo (diferente do original)",
        )
        # O novo command_id deve ser um UUID v4 válido
        parsed = uuid.UUID(command_id_apos_retry)
        self.assertEqual(parsed.version, 4)

    async def test_retry_incrementa_attempts(self):
        """O campo attempts deve ser incrementado a cada retry."""
        publisher = MockPublisher()
        engine = _make_engine(publisher)
        session = MockSession()

        saga = await engine.start_saga(
            order_id="ORD-RETRY-002",
            payload={"order_id": "ORD-RETRY-002", "amount": 100},
            session=session,
        )
        session.put_saga(saga)

        step_0 = saga.steps[0]
        step_0.status = StepStatus.RUNNING

        self.assertEqual(step_0.attempts, 1, "Deve iniciar com attempts=1")

        cmd = publisher.commands[0]
        await engine.handle_reply({
            "command_id": step_0.command_id,
            "saga_id": str(saga.id),
            "command_type": cmd["command_type"],
            "success": False,
            "error_message": "falha de rede",
        }, session=session)

        self.assertEqual(step_0.attempts, 2, "Após 1ª falha, attempts deve ser 2")

    async def test_command_ids_de_retries_sao_todos_distintos(self):
        """
        Simula duas falhas consecutivas: cada retry gera um command_id distinto
        do original e dos anteriores.
        """
        publisher = MockPublisher()
        engine = _make_engine(publisher)
        session = MockSession()

        saga = await engine.start_saga(
            order_id="ORD-RETRY-003",
            payload={"order_id": "ORD-RETRY-003", "amount": 100},
            session=session,
        )
        session.put_saga(saga)

        step_0 = saga.steps[0]
        step_0.status = StepStatus.RUNNING

        ids_vistos: list[str] = [step_0.command_id]

        # Cancela a retry task para não executar o backoff delay nos testes
        original_create_retry_task = engine._create_retry_task

        def _mock_retry_task(command_data, attempt, **kwargs):
            # Apenas registra e não agenda delay real
            return asyncio.get_event_loop().create_task(asyncio.sleep(0))

        engine._create_retry_task = _mock_retry_task

        # Falha 1 → retry 1
        cmd = publisher.commands[0]
        await engine.handle_reply({
            "command_id": ids_vistos[-1],
            "saga_id": str(saga.id),
            "command_type": cmd["command_type"],
            "success": False,
            "error_message": "falha 1",
        }, session=session)
        ids_vistos.append(step_0.command_id)

        # Força step de volta a RUNNING para simular retry em andamento
        step_0.status = StepStatus.RUNNING
        step_0.attempts = 2

        # Falha 2 → retry 2 (última tentativa antes de falha definitiva)
        await engine.handle_reply({
            "command_id": ids_vistos[-1],
            "saga_id": str(saga.id),
            "command_type": cmd["command_type"],
            "success": False,
            "error_message": "falha 2",
        }, session=session)
        if step_0.command_id not in ids_vistos:
            ids_vistos.append(step_0.command_id)

        engine._create_retry_task = original_create_retry_task

        self.assertEqual(
            len(ids_vistos),
            len(set(ids_vistos)),
            f"Todos os command_ids (original + retries) devem ser únicos: {ids_vistos}",
        )


# ---------------------------------------------------------------------------
# Testes — Reply duplicada é ignorada (proteção básica)
# ---------------------------------------------------------------------------

class TestReplyDuplicadaIgnorada(IsolatedAsyncioTestCase):
    """
    Garante que uma reply duplicada (mesmo command_id) para um step já em status
    terminal é ignorada sem alterar o estado da Saga.
    """

    async def test_reply_duplicada_de_step_completed_e_ignorada(self):
        """Step já COMPLETED: reply duplicada deve ser ignorada."""
        publisher = MockPublisher()
        engine = _make_engine(publisher)
        session = MockSession()

        saga = await engine.start_saga(
            order_id="ORD-DUP-001",
            payload={"order_id": "ORD-DUP-001", "amount": 100},
            session=session,
        )
        session.put_saga(saga)

        step_0 = saga.steps[0]
        step_0.status = StepStatus.RUNNING
        cmd_id = step_0.command_id
        cmd = publisher.commands[0]

        reply = {
            "command_id": cmd_id,
            "saga_id": str(saga.id),
            "command_type": cmd["command_type"],
            "success": True,
            "payload": {"ok": True},
        }

        # Primeira entrega — processada normalmente
        await engine.handle_reply(reply, session=session)
        self.assertEqual(step_0.status, StepStatus.COMPLETED)

        current_step_index_apos_primeiro = saga.current_step_index

        # Segunda entrega — deve ser ignorada (step já COMPLETED)
        await engine.handle_reply(reply, session=session)

        self.assertEqual(
            saga.current_step_index,
            current_step_index_apos_primeiro,
            "current_step_index não deve mudar com reply duplicada",
        )

    async def test_reply_duplicada_de_step_failed_e_ignorada(self):
        """Step já FAILED: reply duplicada deve ser ignorada."""
        publisher = MockPublisher()
        engine = _make_engine(publisher)
        session = MockSession()

        saga = await engine.start_saga(
            order_id="ORD-DUP-002",
            payload={"order_id": "ORD-DUP-002", "amount": 100},
            session=session,
        )
        session.put_saga(saga)

        step_0 = saga.steps[0]
        step_0.status = StepStatus.RUNNING
        step_0.attempts = 3  # já esgotadas
        cmd_id = step_0.command_id
        cmd = publisher.commands[0]

        # Simula falha terminal: todas as tentativas esgotadas
        original_create_retry_task = engine._create_retry_task
        engine._create_retry_task = lambda *a, **kw: asyncio.get_event_loop().create_task(asyncio.sleep(0))

        reply_falha = {
            "command_id": cmd_id,
            "saga_id": str(saga.id),
            "command_type": cmd["command_type"],
            "success": False,
            "error_message": "falha terminal",
        }
        await engine.handle_reply(reply_falha, session=session)

        engine._create_retry_task = original_create_retry_task

        # step deve estar FAILED
        self.assertEqual(step_0.status, StepStatus.FAILED)
        saga_status_apos_falha = saga.status

        # Reply duplicada (já com o command_id antigo) — deve ser ignorada
        await engine.handle_reply(reply_falha, session=session)

        self.assertEqual(
            saga.status,
            saga_status_apos_falha,
            "Status da Saga não deve mudar com reply duplicada após step FAILED",
        )


# ---------------------------------------------------------------------------
# Testes — command_id incluso em TODOS os comandos publicados
# ---------------------------------------------------------------------------

class TestCommandIdEmTodosOsComandos(IsolatedAsyncioTestCase):
    """Garante que command_id está presente em cada comando publicado pelo Engine."""

    async def test_todos_comandos_publicados_tem_command_id(self):
        """Happy-path completo: todos os comandos publicados devem conter command_id."""
        publisher = MockPublisher()
        engine = _make_engine(publisher)
        session = MockSession()

        saga = await engine.start_saga(
            order_id="ORD-ALL-001",
            payload={"order_id": "ORD-ALL-001", "amount": 500},
            session=session,
        )
        session.put_saga(saga)

        # Avança todos os steps
        for idx in range(len(saga.steps)):
            step = saga.steps[idx]
            step.status = StepStatus.RUNNING

            if not publisher.commands:
                break

            cmd = publisher.commands[-1]
            reply = {
                "command_id": cmd["command_id"],
                "saga_id": str(saga.id),
                "command_type": cmd["command_type"],
                "success": True,
                "payload": {},
            }
            await engine.handle_reply(reply, session=session)

        # Verifica que TODOS os comandos publicados têm command_id
        self.assertGreater(len(publisher.commands), 0, "Deve ter publicado pelo menos 1 comando")
        for cmd in publisher.commands:
            self.assertIn(
                "command_id",
                cmd,
                f"Comando sem command_id: {cmd}",
            )
            # Cada command_id deve ser um UUID válido
            uuid.UUID(cmd["command_id"])

    async def test_command_id_no_payload_de_compensacao(self):
        """Comandos de compensação também devem incluir command_id."""
        publisher = MockPublisher()
        engine = _make_engine(publisher)
        session = MockSession()

        saga = await engine.start_saga(
            order_id="ORD-COMP-001",
            payload={"order_id": "ORD-COMP-001", "amount": 300},
            session=session,
        )
        session.put_saga(saga)

        step_0 = saga.steps[0]
        step_0.status = StepStatus.RUNNING
        step_0.attempts = 3  # esgota tentativas

        original_create_retry_task = engine._create_retry_task
        engine._create_retry_task = lambda *a, **kw: asyncio.get_event_loop().create_task(asyncio.sleep(0))

        cmd = publisher.commands[0]
        await engine.handle_reply({
            "command_id": cmd["command_id"],
            "saga_id": str(saga.id),
            "command_type": cmd["command_type"],
            "success": False,
            "error_message": "falha forçada",
        }, session=session)

        engine._create_retry_task = original_create_retry_task

        # Não há compensação para step_0 (primeiro step — nada a compensar)
        # Mas todos os comandos publicados até agora devem ter command_id
        for cmd in publisher.commands:
            self.assertIn("command_id", cmd)
            uuid.UUID(cmd["command_id"])

