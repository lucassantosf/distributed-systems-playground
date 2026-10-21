from typing import Tuple


def handle_despachar_pedido(payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """
    Handler para comando de execução: DespacharPedido.
    Gera tracking_code para o pedido.
    """
    order_id = str(payload.get("order_id", ""))
    return True, {"tracking_code": f"TRK-{order_id[:8].upper()}"}, None


def handle_cancelar_despacho(payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """
    Handler para comando de compensação: CancelarDespacho.
    Cancela o despacho e atualiza o status para shipping_cancelled.
    """
    return True, {"status": "shipping_cancelled"}, None


# Handlers registrados no worker de Shipping
COMMAND_HANDLERS = {
    "DespacharPedido": handle_despachar_pedido,
    "CancelarDespacho": handle_cancelar_despacho,
}


def apply_business_rules(command_type: str, payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """
    Função pura que despacha para o handler específico (execução ou compensação).
    Ambos os tipos de comandos são tratados na mesma fila 'shipping.commands'.
    """
    handler = COMMAND_HANDLERS.get(command_type)
    if not handler:
        return False, {}, f"Comando '{command_type}' não suportado pelo serviço shipping"

    return handler(payload, attempt)


