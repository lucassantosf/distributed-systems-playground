from typing import Tuple


def handle_processar_pagamento(payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """
    Handler para comando de execução: ProcessarPagamento.
    - Falha transitória: order_id terminando em '77' falha nas tentativas 1 e 2, sucesso na 3ª.
    - Recusa por limite: total_amount > 9999.99.
    """
    total_amount = float(payload.get("total_amount", 0.0))
    order_id = str(payload.get("order_id", ""))

    if order_id.endswith("77") and attempt < 3:
        return False, {}, f"Erro transitório no gateway de pagamento (tentativa {attempt}/3)"

    if total_amount > 9999.99:
        return False, {}, "Pagamento recusado: valor excede limite de crédito"

    return True, {"transaction_id": f"tx_{order_id}_{attempt}", "status": "approved"}, None


def handle_estornar_pagamento(payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """
    Handler para comando de compensação: EstornarPagamento.
    Devolve o estorno com refund_id gerado.
    """
    order_id = str(payload.get("order_id", ""))
    return True, {"refund_id": f"ref_{order_id}", "status": "refunded"}, None


# Handlers registrados no worker de Payment
COMMAND_HANDLERS = {
    "ProcessarPagamento": handle_processar_pagamento,
    "EstornarPagamento": handle_estornar_pagamento,
}


def apply_business_rules(command_type: str, payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    """
    Função pura que despacha para o handler específico (execução ou compensação).
    Ambos os tipos de comandos são tratados na mesma fila 'payment.commands'.
    """
    handler = COMMAND_HANDLERS.get(command_type)
    if not handler:
        return False, {}, f"Comando '{command_type}' não suportado pelo serviço payment"

    return handler(payload, attempt)


