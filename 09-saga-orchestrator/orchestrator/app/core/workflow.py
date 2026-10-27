import os
from dataclasses import dataclass, field
from typing import List, Optional

# Defaults razoáveis para produção (Card 5.4)
# No docker-compose.yml estes valores são acelerados (ex: 5s / 0.5s) para testes rápidos
def load_env_defaults():
    return {
        "STEP_TIMEOUT_SECONDS": int(os.getenv("STEP_TIMEOUT_SECONDS", "30")),
        "STEP_MAX_ATTEMPTS": int(os.getenv("STEP_MAX_ATTEMPTS", "3")),
        "RETRY_BASE_DELAY_SECONDS": float(os.getenv("RETRY_BASE_DELAY_SECONDS", "1.0")),
    }


_DEFAULTS = load_env_defaults()
DEFAULT_STEP_TIMEOUT_SECONDS = _DEFAULTS["STEP_TIMEOUT_SECONDS"]
DEFAULT_STEP_MAX_ATTEMPTS = _DEFAULTS["STEP_MAX_ATTEMPTS"]
DEFAULT_RETRY_BASE_DELAY = _DEFAULTS["RETRY_BASE_DELAY_SECONDS"]


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


def create_order_workflow(
    step_timeout_seconds: Optional[int] = None,
    step_max_attempts: Optional[int] = None,
) -> WorkflowDefinition:
    """
    Factory para criar a definição do workflow ProcessarPedido com parâmetros
    customizados ou derivados das variáveis de ambiente.
    """
    timeout = step_timeout_seconds if step_timeout_seconds is not None else DEFAULT_STEP_TIMEOUT_SECONDS
    max_attempts = step_max_attempts if step_max_attempts is not None else DEFAULT_STEP_MAX_ATTEMPTS

    return WorkflowDefinition(
        name="ProcessarPedido",
        steps=[
            StepDefinition(
                name="ReservarEstoque",
                service="inventory",
                command_type="ReservarEstoque",
                compensation_command="LiberarEstoque",
                timeout_seconds=timeout,
                max_attempts=max_attempts,
            ),
            StepDefinition(
                name="ProcessarPagamento",
                service="payment",
                command_type="ProcessarPagamento",
                compensation_command="EstornarPagamento",
                timeout_seconds=timeout,
                max_attempts=max_attempts,
            ),
            StepDefinition(
                name="DespacharPedido",
                service="shipping",
                command_type="DespacharPedido",
                compensation_command="CancelarDespacho",
                timeout_seconds=timeout,
                max_attempts=max_attempts,
            ),
            StepDefinition(
                name="NotificarCliente",
                service="notification",
                command_type="NotificarCliente",
                compensation_command=None,  # Fire-and-forget: sem compensação direta
                timeout_seconds=timeout,
                max_attempts=max_attempts,
            ),
        ],
    )


# Definição canônica do workflow ProcessarPedido (E-commerce Saga)
ORDER_WORKFLOW = create_order_workflow()

