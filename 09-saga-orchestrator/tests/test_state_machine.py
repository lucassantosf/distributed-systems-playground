"""
Testes unitários para state_machine.py — Card 2.3.

Cobre:
  - Todas as transições válidas de SagaStateMachine
  - Todas as transições válidas de StepStateMachine
  - InvalidTransitionError levantada em transições ilegais
  - can_transition retorna False sem levantar exceção
  - Estados terminais não aceitam nenhuma transição
"""
import sys
import os
import unittest

# Permite importar os módulos do orchestrator sem instalação
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))

from app.core.enums import SagaStatus, StepStatus
from app.core.state_machine import (
    SagaStateMachine,
    StepStateMachine,
    InvalidTransitionError,
)


# ---------------------------------------------------------------------------
# Stubs simples (sem SQLAlchemy, sem DB)
# ---------------------------------------------------------------------------

class _FakeSaga:
    def __init__(self, status: SagaStatus):
        self.status = status


class _FakeStep:
    def __init__(self, status: StepStatus):
        self.status = status


# ---------------------------------------------------------------------------
# SagaStateMachine
# ---------------------------------------------------------------------------

class TestSagaStateMachineTransitions(unittest.TestCase):

    # ---- Transições válidas ------------------------------------------------

    def test_started_para_running(self):
        saga = _FakeSaga(SagaStatus.STARTED)
        SagaStateMachine.transition(saga, SagaStatus.RUNNING)
        self.assertEqual(saga.status, SagaStatus.RUNNING)

    def test_running_para_completed(self):
        saga = _FakeSaga(SagaStatus.RUNNING)
        SagaStateMachine.transition(saga, SagaStatus.COMPLETED)
        self.assertEqual(saga.status, SagaStatus.COMPLETED)

    def test_running_para_compensating(self):
        saga = _FakeSaga(SagaStatus.RUNNING)
        SagaStateMachine.transition(saga, SagaStatus.COMPENSATING)
        self.assertEqual(saga.status, SagaStatus.COMPENSATING)

    def test_running_para_failed(self):
        saga = _FakeSaga(SagaStatus.RUNNING)
        SagaStateMachine.transition(saga, SagaStatus.FAILED)
        self.assertEqual(saga.status, SagaStatus.FAILED)

    def test_compensating_para_compensated(self):
        saga = _FakeSaga(SagaStatus.COMPENSATING)
        SagaStateMachine.transition(saga, SagaStatus.COMPENSATED)
        self.assertEqual(saga.status, SagaStatus.COMPENSATED)

    def test_compensating_para_failed(self):
        saga = _FakeSaga(SagaStatus.COMPENSATING)
        SagaStateMachine.transition(saga, SagaStatus.FAILED)
        self.assertEqual(saga.status, SagaStatus.FAILED)

    # ---- can_transition sem efeito colateral --------------------------------

    def test_can_transition_valido(self):
        self.assertTrue(SagaStateMachine.can_transition(SagaStatus.STARTED, SagaStatus.RUNNING))

    def test_can_transition_invalido(self):
        self.assertFalse(SagaStateMachine.can_transition(SagaStatus.COMPLETED, SagaStatus.RUNNING))

    # ---- Transições inválidas levantam InvalidTransitionError ---------------

    def test_started_para_completed_invalido(self):
        saga = _FakeSaga(SagaStatus.STARTED)
        with self.assertRaises(InvalidTransitionError):
            SagaStateMachine.transition(saga, SagaStatus.COMPLETED)

    def test_completed_e_terminal(self):
        saga = _FakeSaga(SagaStatus.COMPLETED)
        with self.assertRaises(InvalidTransitionError):
            SagaStateMachine.transition(saga, SagaStatus.RUNNING)

    def test_failed_e_terminal(self):
        saga = _FakeSaga(SagaStatus.FAILED)
        with self.assertRaises(InvalidTransitionError):
            SagaStateMachine.transition(saga, SagaStatus.RUNNING)

    def test_compensated_e_terminal(self):
        saga = _FakeSaga(SagaStatus.COMPENSATED)
        with self.assertRaises(InvalidTransitionError):
            SagaStateMachine.transition(saga, SagaStatus.COMPENSATING)

    # ---- Mensagem de erro contém os status ----------------------------------

    def test_mensagem_de_erro(self):
        saga = _FakeSaga(SagaStatus.STARTED)
        try:
            SagaStateMachine.transition(saga, SagaStatus.FAILED)
        except InvalidTransitionError as exc:
            self.assertIn("STARTED", str(exc))
            self.assertIn("FAILED", str(exc))


# ---------------------------------------------------------------------------
# StepStateMachine
# ---------------------------------------------------------------------------

class TestStepStateMachineTransitions(unittest.TestCase):

    # ---- Transições válidas ------------------------------------------------

    def test_pending_para_running(self):
        step = _FakeStep(StepStatus.PENDING)
        StepStateMachine.transition(step, StepStatus.RUNNING)
        self.assertEqual(step.status, StepStatus.RUNNING)

    def test_running_para_completed(self):
        step = _FakeStep(StepStatus.RUNNING)
        StepStateMachine.transition(step, StepStatus.COMPLETED)
        self.assertEqual(step.status, StepStatus.COMPLETED)

    def test_running_para_failed(self):
        step = _FakeStep(StepStatus.RUNNING)
        StepStateMachine.transition(step, StepStatus.FAILED)
        self.assertEqual(step.status, StepStatus.FAILED)

    def test_failed_para_running_retry(self):
        step = _FakeStep(StepStatus.FAILED)
        StepStateMachine.transition(step, StepStatus.RUNNING)
        self.assertEqual(step.status, StepStatus.RUNNING)

    def test_completed_para_compensating(self):
        step = _FakeStep(StepStatus.COMPLETED)
        StepStateMachine.transition(step, StepStatus.COMPENSATING)
        self.assertEqual(step.status, StepStatus.COMPENSATING)

    def test_compensating_para_compensated(self):
        step = _FakeStep(StepStatus.COMPENSATING)
        StepStateMachine.transition(step, StepStatus.COMPENSATED)
        self.assertEqual(step.status, StepStatus.COMPENSATED)

    def test_compensating_para_compensating_failed(self):
        step = _FakeStep(StepStatus.COMPENSATING)
        StepStateMachine.transition(step, StepStatus.COMPENSATING_FAILED)
        self.assertEqual(step.status, StepStatus.COMPENSATING_FAILED)

    # ---- can_transition sem efeito colateral --------------------------------

    def test_can_transition_valido(self):
        self.assertTrue(StepStateMachine.can_transition(StepStatus.PENDING, StepStatus.RUNNING))

    def test_can_transition_invalido(self):
        self.assertFalse(StepStateMachine.can_transition(StepStatus.PENDING, StepStatus.COMPLETED))

    # ---- Transições inválidas levantam InvalidTransitionError ---------------

    def test_pending_para_completed_invalido(self):
        step = _FakeStep(StepStatus.PENDING)
        with self.assertRaises(InvalidTransitionError):
            StepStateMachine.transition(step, StepStatus.COMPLETED)

    def test_completed_e_terminal_exceto_compensating(self):
        step = _FakeStep(StepStatus.COMPLETED)
        with self.assertRaises(InvalidTransitionError):
            StepStateMachine.transition(step, StepStatus.FAILED)

    def test_compensated_e_terminal(self):
        step = _FakeStep(StepStatus.COMPENSATED)
        with self.assertRaises(InvalidTransitionError):
            StepStateMachine.transition(step, StepStatus.COMPENSATING)

    def test_compensating_failed_e_terminal(self):
        step = _FakeStep(StepStatus.COMPENSATING_FAILED)
        with self.assertRaises(InvalidTransitionError):
            StepStateMachine.transition(step, StepStatus.COMPENSATING)

    # ---- Mensagem de erro contém os status ----------------------------------

    def test_mensagem_de_erro(self):
        step = _FakeStep(StepStatus.PENDING)
        try:
            StepStateMachine.transition(step, StepStatus.COMPENSATING)
        except InvalidTransitionError as exc:
            self.assertIn("PENDING", str(exc))
            self.assertIn("COMPENSATING", str(exc))

    # ---- Status não muda em caso de erro ------------------------------------

    def test_status_nao_muda_em_transicao_invalida(self):
        step = _FakeStep(StepStatus.PENDING)
        try:
            StepStateMachine.transition(step, StepStatus.FAILED)
        except InvalidTransitionError:
            pass
        self.assertEqual(step.status, StepStatus.PENDING)


if __name__ == "__main__":
    unittest.main()
