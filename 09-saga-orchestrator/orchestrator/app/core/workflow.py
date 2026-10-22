import os
from dataclasses import dataclass, field
from typing import List, Optional

DEFAULT_STEP_TIMEOUT_SECONDS = int(os.getenv("STEP_TIMEOUT_SECONDS", "5"))
DEFAULT_STEP_MAX_ATTEMPTS = int(os.getenv("STEP_MAX_ATTEMPTS", "3"))


@dataclass(frozen=True)
class StepDefinition:
    """
    Definição imutável e declarativa de uma etapa de workflow (Step).
    Permite desacoplar a especificação do fluxo do mecanismo de execução (SagaEngine).
    """
    name: str
    service: str
    command_type: str
    compensation_command: Optional[str] = None
    timeout_seconds: int = DEFAULT_STEP_TIMEOUT_SECONDS
    max_attempts: int = DEFAULT_STEP_MAX_ATTEMPTS
    compensation_max_attempts: int = DEFAULT_STEP_MAX_ATTEMPTS

    @property
    def has_compensation(self) -> bool:
        return self.compensation_command is not None


@dataclass(frozen=True)
class WorkflowDefinition:
    """
    Representa a definição completa de um workflow composto por etapas ordenadas.
    """
    name: str
    steps: List[StepDefinition]

    def get_step_by_index(self, index: int) -> Optional[StepDefinition]:
        if 0 <= index < len(self.steps):
            return self.steps[index]
        return None

    def get_step_by_name(self, name: str) -> Optional[StepDefinition]:
        for step in self.steps:
            if step.name == name:
                return step
        return None

    @property
    def total_steps(self) -> int:
        return len(self.steps)


# Definição canônica do workflow ProcessarPedido (E-commerce Saga)
ORDER_WORKFLOW = WorkflowDefinition(
    name="ProcessarPedido",
    steps=[
        StepDefinition(
            name="ReservarEstoque",
            service="inventory",
            command_type="ReservarEstoque",
            compensation_command="LiberarEstoque",
            timeout_seconds=DEFAULT_STEP_TIMEOUT_SECONDS,
            max_attempts=DEFAULT_STEP_MAX_ATTEMPTS,
        ),
        StepDefinition(
            name="ProcessarPagamento",
            service="payment",
            command_type="ProcessarPagamento",
            compensation_command="EstornarPagamento",
            timeout_seconds=DEFAULT_STEP_TIMEOUT_SECONDS,
            max_attempts=DEFAULT_STEP_MAX_ATTEMPTS,
        ),
        StepDefinition(
            name="DespacharPedido",
            service="shipping",
            command_type="DespacharPedido",
            compensation_command="CancelarDespacho",
            timeout_seconds=DEFAULT_STEP_TIMEOUT_SECONDS,
            max_attempts=DEFAULT_STEP_MAX_ATTEMPTS,
        ),
        StepDefinition(
            name="NotificarCliente",
            service="notification",
            command_type="NotificarCliente",
            compensation_command=None,  # Fire-and-forget: sem compensação direta
            timeout_seconds=DEFAULT_STEP_TIMEOUT_SECONDS,
            max_attempts=DEFAULT_STEP_MAX_ATTEMPTS,
        ),
    ],
)

