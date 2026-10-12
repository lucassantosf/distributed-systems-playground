from typing import Tuple


def apply_business_rules(command_type: str, payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """
    Função pura com regras determinísticas para o serviço de Payment:
    - ProcessarPagamento:
        * Falha transitória simulada: order_id terminando em '77' falha nas tentativas 1 e 2, sucesso na 3ª
        * Recusa por limite: total_amount > 9999.99
    - EstornarPagamento (compensação): sucesso gerando refund_id
    """
    total_amount = float(payload.get("total_amount", 0.0))
    order_id = str(payload.get("order_id", ""))

    if command_type == "ProcessarPagamento":
        if order_id.endswith("77") and attempt < 3:
            return False, {}, f"Erro transitório no gateway de pagamento (tentativa {attempt}/3)"

        if total_amount > 9999.99:
            return False, {}, "Pagamento recusado: valor excede limite de crédito"

        return True, {"transaction_id": f"tx_{order_id}_{attempt}", "status": "approved"}, None

    elif command_type == "EstornarPagamento":
        return True, {"refund_id": f"ref_{order_id}", "status": "refunded"}, None

    return True, {}, None

