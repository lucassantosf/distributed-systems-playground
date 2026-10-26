"""
SagaEngine: Motor de Execução da Saga Orchestration.

O Engine é o único componente que conhece o estado atual da Saga
e decide o próximo passo (avanço, compensação, retry ou finalização).
Toda ação relevante registra um SagaEvent imutável para rastreabilidade completa.
"""
import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Union

from app.core.enums import SagaStatus, StepStatus
from app.core.state_machine import SagaStateMachine, StepStateMachine
from app.core.workflow import ORDER_WORKFLOW, DEFAULT_RETRY_BASE_DELAY, StepDefinition, WorkflowDefinition
from app.models.saga import Saga, SagaStep, SagaEvent

logger = logging.getLogger("saga-engine")


class SagaEngine:
    """
    Motor central de orquestração de Sagas.

    Gerencia o ciclo de vida completo de cada workflow:
      - start_saga: inicia a Saga e despacha o primeiro step
      - handle_reply: processa replies de sucesso/falha dos workers
      - start_compensation: executa compensação ordenada reversa
      - handle_timeout: trata steps que excederam timeout configurado
    """

    def __init__(
        self,
        session_factory=None,
        workflow: WorkflowDefinition = ORDER_WORKFLOW,
        publisher=None,
    ):
        """
        Args:
            session_factory: fábrica de AsyncSession (ex: AsyncSessionLocal).
            workflow: definição do workflow a ser orquestrado.
            publisher: publicador de comandos (objeto com publish_command ou callable).
        """
        self.session_factory = session_factory
        self.workflow = workflow
        self.publisher = publisher
        # Mapa de command_id → asyncio.Task de timeout (Card 5.2)
        # Permite cancelar o timer exatamente quando a reply chega.
        self._timeout_tasks: Dict[str, asyncio.Task] = {}

    # -----------------------------------------------------------------------
    # Helper: Sessão e Persistência
    # -----------------------------------------------------------------------

    def _resolve_session_factory(self):
        if self.session_factory is not None:
            return self.session_factory
        try:
            from app.database import AsyncSessionLocal
            return AsyncSessionLocal
        except Exception:
            return None

    async def _get_saga_by_id(self, session, saga_id: Union[str, uuid.UUID]) -> Optional[Saga]:
        if session is None:
            return None

        # Suporte para session mock / test helper
        if hasattr(session, "get_saga"):
            res = session.get_saga(str(saga_id))
            if asyncio.iscoroutine(res):
                return await res
            return res

        # SQLAlchemy AsyncSession
        try:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            uid = uuid.UUID(str(saga_id)) if isinstance(saga_id, str) else saga_id
            stmt = (
                select(Saga)
                .where(Saga.id == uid)
                .options(selectinload(Saga.steps), selectinload(Saga.events))
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.debug(f"Fallback ao buscar saga_id {saga_id}: {exc}")
            return None

    async def _get_saga_by_order_id(self, session, order_id: str) -> Optional[Saga]:
        if session is None:
            return None

        # Suporte para session mock / test helper
        if hasattr(session, "get_saga_by_order_id"):
            res = session.get_saga_by_order_id(order_id)
            if asyncio.iscoroutine(res):
                return await res
            return res

        # SQLAlchemy AsyncSession
        try:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            stmt = (
                select(Saga)
                .where(Saga.order_id == order_id)
                .options(selectinload(Saga.steps), selectinload(Saga.events))
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.debug(f"Fallback ao buscar order_id {order_id}: {exc}")
            return None

    def _record_event(
        self,
        session,
        saga: Saga,
        event_type: str,
        step: Optional[SagaStep] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> SagaEvent:
        """
        Registra um evento append-only no histórico e adiciona na sessão.
        """
        event = SagaEvent(
            id=uuid.uuid4(),
            saga_id=saga.id,
            step_id=step.id if step else None,
            event_type=event_type,
            event_payload=payload or {},
            created_at=datetime.now(timezone.utc),
        )

        if hasattr(saga, "events") and isinstance(saga.events, list):
            saga.events.append(event)

        if session is not None and hasattr(session, "add"):
            session.add(event)

        logger.info(
            f"[SagaEvent] type={event_type} saga_id={saga.id} "
            f"step={step.step_name if step else 'None'} payload={payload}"
        )
        return event

    async def _publish(self, command_data: Dict[str, Any]) -> None:
        """
        Despacha o comando para o publicador configurado.
        """
        if self.publisher is None:
            logger.debug(f"Nenhum publisher configurado. Comando simulado: {command_data}")
            return

        try:
            if hasattr(self.publisher, "publish_command"):
                res = self.publisher.publish_command(
                    service=command_data["service"],
                    command_type=command_data["command_type"],
                    saga_id=command_data["saga_id"],
                    command_id=command_data["command_id"],
                    attempt=command_data.get("attempt", 1),
                    payload=command_data.get("payload", {}),
                )
                if asyncio.iscoroutine(res):
                    await res
            elif callable(self.publisher):
                res = self.publisher(command_data)
                if asyncio.iscoroutine(res):
                    await res
            elif hasattr(self.publisher, "publish"):
                res = self.publisher.publish(command_data)
                if asyncio.iscoroutine(res):
                    await res
        except Exception as e:
            logger.error(f"Erro ao publicar comando: {e}", exc_info=True)
            raise

    async def _publish_to_dlq(
        self,
        saga: Saga,
        step: SagaStep,
        error_message: str,
    ) -> None:
        """
        Publica notificação na DLQ (saga.dlx -> saga.dlq) quando
        uma compensação falha de forma irrecuperável (exigindo intervenção manual).
        """
        if self.publisher is None:
            return

        try:
            if hasattr(self.publisher, "publish_to_dlq"):
                res = self.publisher.publish_to_dlq(
                    saga_id=saga.id,
                    payload={
                        "order_id": saga.order_id,
                        "step_name": step.step_name,
                        "step_index": step.step_index,
                        "command_id": step.command_id,
                        "attempts": step.attempts,
                        "error_message": error_message,
                        "status": "COMPENSATING_FAILED",
                    },
                    reason="COMPENSATION_FAILED",
                )
                if asyncio.iscoroutine(res):
                    await res
        except Exception as e:
            logger.error(f"Erro ao despachar alerta para DLQ: {e}", exc_info=True)

    async def _schedule_retry(
        self,
        command_data: Dict[str, Any],
        attempt: int,
        base_delay: float = DEFAULT_RETRY_BASE_DELAY,
    ) -> None:
        """
        Agenda a re-publicação de um comando com backoff exponencial e jitter.

        Fórmula: delay = base_delay * 2^(attempt-1) * jitter
        Jitter: fator aleatório uniforme em [0.9, 1.1] (±10%).

        Cada tentativa recebe um delay crescente, evitando sobrecarga em retries
        simultâneos (thundering herd). O comando é publicado após o delay via
        asyncio.create_task, não bloqueando o handle_reply.
        """
        exponent = attempt - 1
        delay = base_delay * (2 ** exponent)
        jitter = random.uniform(0.9, 1.1)
        delay_com_jitter = delay * jitter

        logger.info(
            f"[Retry] Agendando tentativa {attempt} em {delay_com_jitter:.3f}s "
            f"para saga={command_data.get('saga_id')} "
            f"step={command_data.get('command_type')}"
        )

        await asyncio.sleep(delay_com_jitter)
        await self._publish(command_data)
        # Arma watchdog de timeout após a publicação do retry (Card 5.2)
        self._arm_timeout(
            saga_id=command_data.get("saga_id", ""),
            step_index=command_data.get("step_index", -1),
            command_id=command_data.get("command_id", ""),
            timeout_seconds=command_data.get("timeout_seconds", 0),
        )

    def _create_retry_task(
        self,
        command_data: Dict[str, Any],
        attempt: int,
        base_delay: float = DEFAULT_RETRY_BASE_DELAY,
    ) -> asyncio.Task:
        """
        Cria uma asyncio.Task para re-publicar o comando com backoff exponencial.
        Retorna a Task para que o chamador possa cancelá-la se necessário (ex: timeout).
        """
        return asyncio.create_task(
            self._schedule_retry(command_data, attempt, base_delay)
        )

    async def _run_timeout_watchdog(
        self,
        saga_id: str,
        step_index: int,
        command_id: str,
        timeout_seconds: float,
    ) -> None:
        """
        Watchdog de timeout para um step: aguarda `timeout_seconds` e, se a task
        não for cancelada antes (pelo cancel_timeout quando a reply chega),
        aciona handle_timeout para tratar o step como expirado.
        """
        try:
            await asyncio.sleep(timeout_seconds)
            # Se chegou aqui, a reply não chegou a tempo — dispara o timeout
            logger.warning(
                f"[Timeout] Step {step_index} da Saga {saga_id} expirou após "
                f"{timeout_seconds}s (command_id={command_id})"
            )
            await self.handle_timeout(saga_id, step_index)
        except asyncio.CancelledError:
            # Reply chegou antes do timeout — task cancelada corretamente
            logger.debug(
                f"[Timeout] Watchdog cancelado para command_id={command_id} "
                f"(reply recebida antes do timeout)"
            )
        finally:
            # Limpa o mapa independentemente do motivo
            self._timeout_tasks.pop(command_id, None)

    def _arm_timeout(
        self,
        saga_id: str,
        step_index: int,
        command_id: str,
        timeout_seconds: float,
    ) -> None:
        """
        Arma o watchdog de timeout para o command_id fornecido.

        Cria uma asyncio.Task que aguarda timeout_seconds e chama handle_timeout
        se não for cancelada antes. Se timeout_seconds <= 0, o timeout é desabilitado.
        """
        if timeout_seconds <= 0:
            return

        task = asyncio.create_task(
            self._run_timeout_watchdog(saga_id, step_index, command_id, timeout_seconds)
        )
        self._timeout_tasks[command_id] = task
        logger.debug(
            f"[Timeout] Watchdog armado: command_id={command_id} "
            f"saga={saga_id} step={step_index} timeout={timeout_seconds}s"
        )

    def _cancel_timeout(self, command_id: str) -> None:
        """
        Cancela o watchdog de timeout associado ao command_id, se existir.
        Chamado quando a reply de um comando chega antes do timeout expirar.
        """
        task = self._timeout_tasks.pop(command_id, None)
        if task and not task.done():
            task.cancel()
            logger.debug(f"[Timeout] Watchdog cancelado para command_id={command_id}")

    # -----------------------------------------------------------------------
    # Método 1: start_saga
    # -----------------------------------------------------------------------

    async def start_saga(
        self,
        order_id: str,
        payload: Dict[str, Any],
        session=None,
    ) -> Saga:
        """
        Inicia uma nova Saga:
          1. Verifica idempotência (se já existe saga para o order_id)
          2. Cria registro Saga (STARTED) e todos os SagaStep (PENDING)
          3. Registra evento SagaStarted
          4. Transiciona Saga para RUNNING
          5. Transiciona Step 0 para RUNNING e despacha seu comando
          6. Registra evento StepStarted
        """
        if session is None:
            factory = self._resolve_session_factory()
            if factory:
                command_to_publish = None
                async with factory() as s:
                    async with s.begin():
                        saga, command_to_publish = await self._start_saga_core(order_id, payload, session=s)
                # Publica FORA do bloco de transação: garante que a Saga já está COMMITADA no banco
                # antes de qualquer worker receber o comando e responder.
                if command_to_publish:
                    await self._publish(command_to_publish)
                    # Arma o watchdog de timeout para o step 0 (Card 5.2)
                    self._arm_timeout(
                        saga_id=command_to_publish["saga_id"],
                        step_index=command_to_publish.get("step_index", 0),
                        command_id=command_to_publish["command_id"],
                        timeout_seconds=command_to_publish.get("timeout_seconds", 0),
                    )
                return saga

        saga, command_to_publish = await self._start_saga_core(order_id, payload, session=session)
        if command_to_publish:
            await self._publish(command_to_publish)
            # Arma o watchdog de timeout para o step 0 (Card 5.2)
            self._arm_timeout(
                saga_id=command_to_publish["saga_id"],
                step_index=command_to_publish.get("step_index", 0),
                command_id=command_to_publish["command_id"],
                timeout_seconds=command_to_publish.get("timeout_seconds", 0),
            )
        return saga

    async def _start_saga_core(
        self,
        order_id: str,
        payload: Dict[str, Any],
        session=None,
    ) -> tuple[Saga, Optional[Dict[str, Any]]]:
        # 1. Idempotência a nível de order_id
        existing = await self._get_saga_by_order_id(session, order_id)
        if existing:
            logger.info(f"Saga já existente para order_id '{order_id}': id={existing.id}")
            return existing, None

        now = datetime.now(timezone.utc)
        saga_id = uuid.uuid4()

        # 2. Cria a Saga
        saga = Saga(
            id=saga_id,
            order_id=order_id,
            status=SagaStatus.STARTED,
            current_step_index=0,
            payload=payload,
            created_at=now,
            updated_at=now,
        )

        # Cria todos os steps da definição
        steps: List[SagaStep] = []
        for idx, step_def in enumerate(self.workflow.steps):
            step = SagaStep(
                id=uuid.uuid4(),
                saga_id=saga_id,
                step_name=step_def.name,
                step_index=idx,
                status=StepStatus.PENDING,
                command_id=None,
                attempts=0,
                payload=payload,
                result={},
            )
            step.saga = saga
            steps.append(step)
            if session is not None and hasattr(session, "add"):
                session.add(step)

        saga.steps = steps

        if session is not None and hasattr(session, "add"):
            session.add(saga)

        # 3. Registra SagaStarted
        self._record_event(
            session=session,
            saga=saga,
            event_type="SagaStarted",
            payload={"order_id": order_id, "workflow": self.workflow.name},
        )

        # 4. Transiciona Saga para RUNNING
        SagaStateMachine.transition(saga, SagaStatus.RUNNING)

        # 5. Prepara e inicia o Step 0
        step_0 = steps[0]
        step_def_0 = self.workflow.get_step_by_index(0)

        StepStateMachine.transition(step_0, StepStatus.RUNNING)
        step_0.attempts = 1
        step_0.command_id = str(uuid.uuid4())
        step_0.started_at = now

        # 6. Registra StepStarted
        self._record_event(
            session=session,
            saga=saga,
            step=step_0,
            event_type="StepStarted",
            payload={
                "command_id": step_0.command_id,
                "step_index": 0,
                "step_name": step_0.step_name,
                "command_type": step_def_0.command_type,
                "service": step_def_0.service,
                "attempt": step_0.attempts,
            },
        )

        command_dict = {
            "service": step_def_0.service,
            "command_type": step_def_0.command_type,
            "saga_id": str(saga.id),
            "command_id": step_0.command_id,
            "attempt": step_0.attempts,
            "payload": payload,
            # Metadados para armar o timeout após a publicação (Card 5.2)
            "step_index": 0,
            "timeout_seconds": step_def_0.timeout_seconds,
        }

        return saga, command_dict

    # -----------------------------------------------------------------------
    # Método 2: handle_reply
    # -----------------------------------------------------------------------

    async def handle_reply(
        self,
        reply: Dict[str, Any],
        session=None,
    ) -> Optional[Saga]:
        """
        Processa resposta de um worker (sucesso ou falha).

        Estrutura de reply esperada:
        {
            "command_id": str,
            "saga_id": str,
            "command_type": str,
            "service": str,
            "success": bool,
            "payload": dict,
            "error_message": Optional[str],
        }
        """
        if session is None:
            factory = self._resolve_session_factory()
            if factory:
                async with factory() as s:
                    async with s.begin():
                        return await self.handle_reply(reply, session=s)

        saga_id = reply.get("saga_id")
        command_id = reply.get("command_id")
        success = bool(reply.get("success", False))
        error_message = reply.get("error_message")
        result_data = reply.get("payload") or {}
        command_type = reply.get("command_type")

        saga = await self._get_saga_by_id(session, saga_id)
        if not saga:
            # Tolerância para eventuais transações assíncronas em processo de commit
            await asyncio.sleep(0.05)
            saga = await self._get_saga_by_id(session, saga_id)

        if not saga:
            logger.warning(f"Saga '{saga_id}' não encontrada ao processar reply.")
            return None

        # Localiza o step correspondente pelo command_id
        matching_step: Optional[SagaStep] = None
        for step in saga.steps:
            if step.command_id == command_id:
                matching_step = step
                break

        if not matching_step:
            # Fallback por índice atual se command_id não bater
            if 0 <= saga.current_step_index < len(saga.steps):
                candidate = saga.steps[saga.current_step_index]
                step_def = self.workflow.get_step_by_index(candidate.step_index)
                if step_def and (
                    step_def.command_type == command_type
                    or step_def.compensation_command == command_type
                ):
                    matching_step = candidate

        if not matching_step:
            logger.warning(
                f"Nenhum step encontrado para command_id={command_id} na Saga {saga_id}."
            )
            return saga

        now = datetime.now(timezone.utc)

        # Cancela o watchdog de timeout para este command_id (Card 5.2):
        # a reply chegou a tempo, então o timer não deve disparar.
        self._cancel_timeout(command_id)

        # Proteção contra respostas duplicadas / tardias (Card 6.3)
        if matching_step.status in (
            StepStatus.COMPLETED,
            StepStatus.COMPENSATED,
            StepStatus.COMPENSATING_FAILED,
        ):
            logger.info(
                f"Reply duplicada/tardia ignorada: step {matching_step.step_name} "
                f"já está em status terminal {matching_step.status}."
            )
            return saga

        # -------------------------------------------------------------------
        # Cenário A: Resposta para execução normal (RUNNING)
        # -------------------------------------------------------------------
        if matching_step.status == StepStatus.RUNNING:
            if success:
                # Transiciona step para COMPLETED
                StepStateMachine.transition(matching_step, StepStatus.COMPLETED)
                matching_step.completed_at = now
                matching_step.result = result_data

                self._record_event(
                    session=session,
                    saga=saga,
                    step=matching_step,
                    event_type="StepCompleted",
                    payload={"command_type": command_type, "result": result_data},
                )

                # Avalia próximo step
                next_index = matching_step.step_index + 1
                if next_index < self.workflow.total_steps:
                    # Avança para o próximo step
                    saga.current_step_index = next_index
                    next_step = saga.steps[next_index]
                    next_step_def = self.workflow.get_step_by_index(next_index)

                    StepStateMachine.transition(next_step, StepStatus.RUNNING)
                    next_step.attempts = 1
                    next_step.command_id = str(uuid.uuid4())
                    next_step.started_at = now

                    self._record_event(
                        session=session,
                        saga=saga,
                        step=next_step,
                        event_type="StepStarted",
                        payload={
                            "command_id": next_step.command_id,
                            "step_name": next_step.step_name,
                            "step_index": next_index,
                            "command_type": next_step_def.command_type,
                            "service": next_step_def.service,
                            "attempt": next_step.attempts,
                        },
                    )

                    await self._publish({
                        "service": next_step_def.service,
                        "command_type": next_step_def.command_type,
                        "saga_id": str(saga.id),
                        "command_id": next_step.command_id,
                        "attempt": next_step.attempts,
                        "payload": next_step.payload or saga.payload,
                    })
                    # Arma o watchdog de timeout para o próximo step (Card 5.2)
                    self._arm_timeout(
                        saga_id=str(saga.id),
                        step_index=next_index,
                        command_id=next_step.command_id,
                        timeout_seconds=next_step_def.timeout_seconds,
                    )
                else:
                    # Todos os steps concluídos com sucesso!
                    SagaStateMachine.transition(saga, SagaStatus.COMPLETED)
                    saga.completed_at = now
                    self._record_event(
                        session=session,
                        saga=saga,
                        event_type="SagaCompleted",
                        payload={"order_id": saga.order_id},
                    )

            else:
                # Falha na execução normal
                step_def = self.workflow.get_step_by_index(matching_step.step_index)
                max_attempts = step_def.max_attempts if step_def else 1

                # Se ainda há tentativas e retry estiver habilitado
                if matching_step.attempts < max_attempts:
                    matching_step.attempts += 1
                    matching_step.command_id = str(uuid.uuid4())
                    matching_step.started_at = now

                    self._record_event(
                        session=session,
                        saga=saga,
                        step=matching_step,
                        event_type="StepRetried",
                        payload={
                            "command_id": matching_step.command_id,
                            "attempt": matching_step.attempts,
                            "max_attempts": max_attempts,
                            "error": error_message,
                        },
                    )

                    # Retry com backoff exponencial (Card 5.1):
                    # Agenda re-publicação via asyncio.create_task para não bloquear
                    # o handle_reply enquanto o delay transcorre.
                    self._create_retry_task(
                        command_data={
                            "service": step_def.service,
                            "command_type": step_def.command_type,
                            "saga_id": str(saga.id),
                            "command_id": matching_step.command_id,
                            "attempt": matching_step.attempts,
                            "payload": matching_step.payload or saga.payload,
                            # Inclui metadados para armar o timeout após o publish (Card 5.2)
                            "step_index": matching_step.step_index,
                            "timeout_seconds": step_def.timeout_seconds,
                        },
                        attempt=matching_step.attempts,
                    )
                else:
                    # Tentativas esgotadas: falha o step e inicia compensação
                    StepStateMachine.transition(matching_step, StepStatus.FAILED)
                    matching_step.failed_at = now
                    matching_step.error_message = error_message or "Falha na execução do step"

                    self._record_event(
                        session=session,
                        saga=saga,
                        step=matching_step,
                        event_type="StepFailed",
                        payload={
                            "error": matching_step.error_message,
                            "attempts": matching_step.attempts,
                        },
                    )

                    await self.start_compensation(saga, session=session)

        # -------------------------------------------------------------------
        # Cenário B: Resposta para compensação (COMPENSATING)
        # -------------------------------------------------------------------
        elif matching_step.status == StepStatus.COMPENSATING:
            if success:
                StepStateMachine.transition(matching_step, StepStatus.COMPENSATED)
                matching_step.completed_at = now

                self._record_event(
                    session=session,
                    saga=saga,
                    step=matching_step,
                    event_type="StepCompensated",
                    payload={"command_type": command_type},
                )

                # Aciona o próximo step a ser compensado em ordem decrescente
                await self._trigger_next_compensation(saga, session=session)
            else:
                step_def = self.workflow.get_step_by_index(matching_step.step_index)
                max_attempts = getattr(
                    step_def,
                    "compensation_max_attempts",
                    getattr(step_def, "max_attempts", 3) if step_def else 1,
                )

                if matching_step.attempts < max_attempts:
                    matching_step.attempts += 1
                    matching_step.command_id = str(uuid.uuid4())
                    matching_step.started_at = now

                    comp_command = step_def.compensation_command if step_def else command_type

                    self._record_event(
                        session=session,
                        saga=saga,
                        step=matching_step,
                        event_type="StepCompensationRetried",
                        payload={
                            "command_id": matching_step.command_id,
                            "attempt": matching_step.attempts,
                            "max_attempts": max_attempts,
                            "error": error_message,
                            "command_type": comp_command,
                        },
                    )

                    # Retry com backoff exponencial (Card 5.1):
                    # Agenda re-publicação via asyncio.create_task para não bloquear
                    # o handle_reply enquanto o delay transcorre.
                    self._create_retry_task(
                        command_data={
                            "service": step_def.service if step_def else "unknown",
                            "command_type": comp_command,
                            "saga_id": str(saga.id),
                            "command_id": matching_step.command_id,
                            "attempt": matching_step.attempts,
                            "payload": matching_step.payload or saga.payload,
                        },
                        attempt=matching_step.attempts,
                    )
                else:
                    # Falha irrecuperável na compensação (todas as tentativas esgotadas)
                    StepStateMachine.transition(matching_step, StepStatus.COMPENSATING_FAILED)
                    matching_step.failed_at = now
                    matching_step.error_message = error_message or "Falha na compensação do step"

                    SagaStateMachine.transition(saga, SagaStatus.FAILED)
                    saga.completed_at = now

                    self._record_event(
                        session=session,
                        saga=saga,
                        step=matching_step,
                        event_type="StepCompensationFailed",
                        payload={
                            "error": matching_step.error_message,
                            "attempts": matching_step.attempts,
                        },
                    )
                    self._record_event(
                        session=session,
                        saga=saga,
                        event_type="SagaFailed",
                        payload={
                            "reason": "Falha irrecuperável em compensação",
                            "order_id": saga.order_id,
                        },
                    )

                    await self._publish_to_dlq(saga, matching_step, matching_step.error_message)

        return saga

    # -----------------------------------------------------------------------
    # Método 3: start_compensation
    # -----------------------------------------------------------------------

    async def start_compensation(
        self,
        saga_or_id: Union[str, uuid.UUID, Saga],
        session=None,
    ) -> Saga:
        """
        Inicia a compensação da Saga:
          1. Transiciona a Saga para COMPENSATING
          2. Filtra steps COMPLETED que possuem compensation_command
          3. Dispara a compensação em ordem decrescente de step_index
          4. Se nenhum step requer compensação, transiciona diretamente para COMPENSATED
        """
        if session is None:
            factory = self._resolve_session_factory()
            if factory:
                async with factory() as s:
                    async with s.begin():
                        return await self.start_compensation(saga_or_id, session=s)

        if isinstance(saga_or_id, Saga):
            saga = saga_or_id
        else:
            saga = await self._get_saga_by_id(session, saga_or_id)
            if not saga:
                raise ValueError(f"Saga '{saga_or_id}' não encontrada para compensação.")

        if SagaStateMachine.can_transition(saga.status, SagaStatus.COMPENSATING):
            SagaStateMachine.transition(saga, SagaStatus.COMPENSATING)
            self._record_event(
                session=session,
                saga=saga,
                event_type="SagaCompensating",
                payload={"order_id": saga.order_id},
            )

        await self._trigger_next_compensation(saga, session=session)
        return saga

    async def _trigger_next_compensation(self, saga: Saga, session=None) -> None:
        """
        Localiza o próximo step em status COMPLETED (em ordem reversa)
        que possua compensation_command e inicia sua compensação.
        Se nenhum step restar, marca a Saga como COMPENSATED.
        """
        # Filtra steps completados que possuem comando de compensação
        completed_steps: List[SagaStep] = []
        for step in saga.steps:
            if step.status == StepStatus.COMPLETED:
                step_def = self.workflow.get_step_by_index(step.step_index)
                if step_def and step_def.has_compensation:
                    completed_steps.append(step)

        # Ordem decrescente de índice (LIFO / rollback reverso)
        completed_steps.sort(key=lambda s: s.step_index, reverse=True)

        if not completed_steps:
            # Todos os passos necessários já foram compensados
            now = datetime.now(timezone.utc)
            if SagaStateMachine.can_transition(saga.status, SagaStatus.COMPENSATED):
                SagaStateMachine.transition(saga, SagaStatus.COMPENSATED)
                saga.completed_at = now
                self._record_event(
                    session=session,
                    saga=saga,
                    event_type="SagaCompensated",
                    payload={"order_id": saga.order_id},
                )
            return

        # Pega o primeiro da lista reversa
        step_to_compensate = completed_steps[0]
        step_def = self.workflow.get_step_by_index(step_to_compensate.step_index)

        now = datetime.now(timezone.utc)
        StepStateMachine.transition(step_to_compensate, StepStatus.COMPENSATING)
        step_to_compensate.command_id = str(uuid.uuid4())
        step_to_compensate.attempts = 1
        step_to_compensate.started_at = now

        self._record_event(
            session=session,
            saga=saga,
            step=step_to_compensate,
            event_type="StepCompensationStarted",
            payload={
                "command_id": step_to_compensate.command_id,
                "command_type": step_def.compensation_command,
                "step_index": step_to_compensate.step_index,
                "service": step_def.service,
            },
        )

        await self._publish({
            "service": step_def.service,
            "command_type": step_def.compensation_command,
            "saga_id": str(saga.id),
            "command_id": step_to_compensate.command_id,
            "attempt": step_to_compensate.attempts,
            "payload": step_to_compensate.payload or saga.payload,
        })

    # -----------------------------------------------------------------------
    # Método 4: handle_timeout
    # -----------------------------------------------------------------------

    async def handle_timeout(
        self,
        saga_id: Union[str, uuid.UUID],
        step_index: int,
        session=None,
    ) -> Optional[Saga]:
        """
        Trata timeout de execução de um step:
          1. Verifica se o step ainda está em status RUNNING
          2. Se já estiver completado ou falhado, ignora (reply chegou a tempo)
          3. Registra evento StepTimeout e StepFailed
          4. Transiciona step para FAILED
          5. Inicia compensação da Saga
        """
        if session is None:
            factory = self._resolve_session_factory()
            if factory:
                async with factory() as s:
                    async with s.begin():
                        return await self.handle_timeout(saga_id, step_index, session=s)

        saga = await self._get_saga_by_id(session, saga_id)
        if not saga:
            logger.warning(f"Saga '{saga_id}' não encontrada ao processar timeout.")
            return None

        # Localiza o step
        step: Optional[SagaStep] = None
        for s in saga.steps:
            if s.step_index == step_index:
                step = s
                break

        if not step:
            logger.warning(f"Step de índice {step_index} não encontrado na Saga '{saga_id}'.")
            return saga

        # Se não está RUNNING, o timeout é irrelevante
        if step.status != StepStatus.RUNNING:
            logger.info(
                f"Timeout ignorado: step {step.step_name} (índice {step_index}) "
                f"da Saga {saga_id} já está em status {step.status}."
            )
            return saga

        step_def = self.workflow.get_step_by_index(step_index)
        timeout_sec = step_def.timeout_seconds if step_def else 0
        now = datetime.now(timezone.utc)

        # Registra StepTimeout
        self._record_event(
            session=session,
            saga=saga,
            step=step,
            event_type="StepTimeout",
            payload={"step_index": step_index, "timeout_seconds": timeout_sec},
        )

        # Transiciona step para FAILED
        StepStateMachine.transition(step, StepStatus.FAILED)
        step.failed_at = now
        step.error_message = f"Timeout de {timeout_sec}s expirado sem resposta"

        self._record_event(
            session=session,
            saga=saga,
            step=step,
            event_type="StepFailed",
            payload={"error": step.error_message, "reason": "TIMEOUT"},
        )

        # Inicia compensação para rollback dos steps anteriores
        await self.start_compensation(saga, session=session)
        return saga

