"""
Enums de status de Saga e SagaStep.

Módulo sem dependências externas — pode ser importado em testes
locais sem SQLAlchemy instalado.
"""
import enum


class SagaStatus(str, enum.Enum):
    STARTED      = "STARTED"
    RUNNING      = "RUNNING"
    COMPLETED    = "COMPLETED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED  = "COMPENSATED"
    FAILED       = "FAILED"


class StepStatus(str, enum.Enum):
    PENDING             = "PENDING"
    RUNNING             = "RUNNING"
    COMPLETED           = "COMPLETED"
    FAILED              = "FAILED"
    COMPENSATING        = "COMPENSATING"
    COMPENSATED         = "COMPENSATED"
    COMPENSATING_FAILED = "COMPENSATING_FAILED"

