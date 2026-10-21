from typing import Tuple


def handle_notificar_cliente(payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """
    Handler para comando de execução: NotificarCliente.
    Fire-and-forget: não possui compensação direta.
    """
    customer_id = payload.get("customer_id")
    return True, {"notified": True, "customer_id": customer_id}, None


# Handlers registrados no worker de Notification
COMMAND_HANDLERS = {
    "NotificarCliente": handle_notificar_cliente,
}


def apply_business_rules(command_type: str, payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """
    Função pura que despacha para o handler específico.
    """
    handler = COMMAND_HANDLERS.get(command_type)
    if not handler:
        return False, {}, f"Comando '{command_type}' não suportado pelo serviço notification"

    return handler(payload, attempt)


