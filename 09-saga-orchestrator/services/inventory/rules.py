from typing import Tuple


def apply_business_rules(command_type: str, payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """
    Função pura com regras determinísticas para o serviço de Inventory:
    - ReservarEstoque: falha se qualquer SKU contiver 'ESGOTADO'
    - LiberarEstoque (compensação): falha fatal se order_id terminar em '66'
    """
    items = payload.get("items", [])
    order_id = str(payload.get("order_id", ""))

    if command_type == "ReservarEstoque":
        for item in items:
            if "ESGOTADO" in str(item.get("sku", "")):
                return False, {}, "Estoque indisponível: produto esgotado"
        return True, {"reserved_items": len(items)}, None

    elif command_type == "LiberarEstoque":
        if order_id.endswith("66"):
            return False, {}, "Falha fatal na compensação do estoque"
        return True, {"status": "stock_released"}, None

    return True, {}, None

