from typing import Tuple


def apply_business_rules(command_type: str, payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """
    Função pura com regras determinísticas para o serviço de Notification:
    - NotificarCliente: fire-and-forget, sempre sucesso
    """
    customer_id = payload.get("customer_id")
    return True, {"notified": True, "customer_id": customer_id}, None

