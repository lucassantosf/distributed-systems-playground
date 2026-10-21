from typing import Tuple


def handle_reservar_estoque(payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """Handler para comando de execução: ReservarEstoque."""
    items = payload.get("items", [])
    for item in items:
        if "ESGOTADO" in str(item.get("sku", "")):
            return False, {}, "Estoque indisponível: produto esgotado"
    return True, {"reserved_items": len(items)}, None


def handle_liberar_estoque(payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """Handler para comando de compensação: LiberarEstoque."""
    order_id = str(payload.get("order_id", ""))
    if order_id.endswith("66"):
        return False, {}, "Falha fatal na compensação do estoque"
    return True, {"status": "stock_released"}, None


# Handlers registrados no worker de Inventory
COMMAND_HANDLERS = {
    "ReservarEstoque": handle_reservar_estoque,
    "LiberarEstoque": handle_liberar_estoque,
}


def apply_business_rules(command_type: str, payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """
    Função pura que despacha para o handler específico (execução ou compensação).
    Ambos os tipos de comandos são tratados na mesma fila 'inventory.commands'.
    """
    handler = COMMAND_HANDLERS.get(command_type)
    if not handler:
        return False, {}, f"Comando '{command_type}' não suportado pelo serviço inventory"

    return handler(payload, attempt)


