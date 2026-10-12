from typing import Tuple


def apply_business_rules(command_type: str, payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """
    Função pura com regras determinísticas para o serviço de Shipping:
    - DespacharPedido: sucesso gerando tracking_code
    - CancelarDespacho (compensação): sucesso com status shipping_cancelled
    """
    order_id = str(payload.get("order_id", ""))

    if command_type == "DespacharPedido":
        return True, {"tracking_code": f"TRK-{order_id[:8].upper()}"}, None

    elif command_type == "CancelarDespacho":
        return True, {"status": "shipping_cancelled"}, None

    return True, {}, None

