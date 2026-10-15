"""
Máquinas de estado para Saga e SagaStep.

Responsabilidade única: validar se uma transição de status é permitida.
Sem efeitos colaterais — pura lógica, sem DB, sem mensagens.
"""
from typing import Dict, FrozenSet
from app.core.enums import SagaStatus, StepStatus


class InvalidTransitionError(Exception):
    """
    Levantada quando uma transição de status ilegal é tentada.

    Exemplos de uso:
        raise InvalidTransitionError(SagaStatus.COMPLETED, SagaStatus.RUNNING)
    """
    def __init__(self, from_status, to_status):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Transição inválida: {from_status.value!r} → {to_status.value!r}"
        )


# ---------------------------------------------------------------------------
# Tabelas de transição
# ---------------------------------------------------------------------------

# SagaStatus: cada estado mapeia para o conjunto de estados destino permitidos
_SAGA_TRANSITIONS: Dict[SagaStatus, FrozenSet[SagaStatus]] = {
    SagaStatus.STARTED:      frozenset({SagaStatus.RUNNING}),
    SagaStatus.RUNNING:      frozenset({SagaStatus.COMPLETED, SagaStatus.COMPENSATING, SagaStatus.FAILED}),
    SagaStatus.COMPENSATING: frozenset({SagaStatus.COMPENSATED, SagaStatus.FAILED}),
    # Estados terminais: sem saída
    SagaStatus.COMPLETED:    frozenset(),
    SagaStatus.COMPENSATED:  frozenset(),
    SagaStatus.FAILED:       frozenset(),
}

# StepStatus: análogo para etapas individuais
_STEP_TRANSITIONS: Dict[StepStatus, FrozenSet[StepStatus]] = {
    StepStatus.PENDING:             frozenset({StepStatus.RUNNING}),
    StepStatus.RUNNING:             frozenset({StepStatus.COMPLETED, StepStatus.FAILED}),
    StepStatus.FAILED:              frozenset({StepStatus.RUNNING}),          # retry
    StepStatus.COMPLETED:           frozenset({StepStatus.COMPENSATING}),
    StepStatus.COMPENSATING:        frozenset({StepStatus.COMPENSATED, StepStatus.COMPENSATING_FAILED}),
    # Estados terminais: sem saída
    StepStatus.COMPENSATED:         frozenset(),
    StepStatus.COMPENSATING_FAILED: frozenset(),
}


# ---------------------------------------------------------------------------
# Máquinas de estado
# ---------------------------------------------------------------------------

class SagaStateMachine:
    """
    Valida transições de status de uma Saga.

    Uso:
        SagaStateMachine.transition(saga, SagaStatus.RUNNING)
        # → atualiza saga.status ou levanta InvalidTransitionError
    """

    @staticmethod
    def can_transition(from_status: SagaStatus, to_status: SagaStatus) -> bool:
        """Retorna True se a transição é permitida."""
        return to_status in _SAGA_TRANSITIONS.get(from_status, frozenset())

    @staticmethod
    def transition(saga, to_status: SagaStatus) -> None:
        """
        Aplica a transição ao objeto Saga.

        Args:
            saga: instância do modelo Saga (com atributo .status).
            to_status: novo status desejado.

        Raises:
            InvalidTransitionError: se a transição não for permitida.
        """
        if not SagaStateMachine.can_transition(saga.status, to_status):
            raise InvalidTransitionError(saga.status, to_status)
        saga.status = to_status


class StepStateMachine:
    """
    Valida transições de status de um SagaStep.

    Uso:
        StepStateMachine.transition(step, StepStatus.COMPLETED)
        # → atualiza step.status ou levanta InvalidTransitionError
    """

    @staticmethod
    def can_transition(from_status: StepStatus, to_status: StepStatus) -> bool:
        """Retorna True se a transição é permitida."""
        return to_status in _STEP_TRANSITIONS.get(from_status, frozenset())

    @staticmethod
    def transition(step, to_status: StepStatus) -> None:
        """
        Aplica a transição ao objeto SagaStep.

        Args:
            step: instância do modelo SagaStep (com atributo .status).
            to_status: novo status desejado.

        Raises:
            InvalidTransitionError: se a transição não for permitida.
        """
        if not StepStateMachine.can_transition(step.status, to_status):
            raise InvalidTransitionError(step.status, to_status)
        step.status = to_status
