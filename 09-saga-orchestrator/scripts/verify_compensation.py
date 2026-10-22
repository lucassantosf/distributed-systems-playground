"""
verify_compensation.py — Validação de Compensação / Rollback End-to-End (Card 4.3)

Roteiro:
  1. POST /sagas com total_amount > 9999.99 (R$ 15.000,00) para forçar recusa de pagamento
  2. Polling até status == COMPENSATED (timeout 30s)
  3. Validação dos status de cada step:
     - Step 0 (ReservarEstoque): COMPENSATED
     - Step 1 (ProcessarPagamento): FAILED com mensagem de limite excedido e attempts == 3
     - Step 2 (DespacharPedido): PENDING (nunca executado)
     - Step 3 (NotificarCliente): PENDING (nunca executado)
  4. Validação da linha do tempo (timeline):
     - Exatamente 11 eventos na ordem canônica
     - Validação dos tipos de eventos e metadados de rollback
  5. Validação de idempotência: segunda chamada retorna a Saga existente

Uso:
  python3 scripts/verify_compensation.py
  python3 scripts/verify_compensation.py --base-url http://localhost:8090
"""
import asyncio
import sys
import time
import uuid
import argparse

try:
    import httpx
except ImportError:
    print("❌ Dependência ausente: instale com 'pip install httpx'")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
POLL_INTERVAL_S = 0.5   # intervalo entre tentativas de polling
POLL_TIMEOUT_S  = 30    # tempo máximo aguardando COMPENSATED

# Sequência canônica de eventos esperada para rollback por limite de crédito:
# Step 0 (ReservarEstoque): Started -> Completed
# Step 1 (ProcessarPagamento): Started -> Retried (tentativa 2) -> Retried (tentativa 3) -> Failed
# Saga: Compensating
# Step 0 (LiberarEstoque): CompensationStarted -> Compensated
# Saga: Compensated
EXPECTED_EVENT_TYPES = [
    "SagaStarted",
    "StepStarted",               # Step 0: ReservarEstoque
    "StepCompleted",             # Step 0: ReservarEstoque
    "StepStarted",               # Step 1: ProcessarPagamento (tentativa 1)
    "StepRetried",               # Step 1: ProcessarPagamento (tentativa 2)
    "StepRetried",               # Step 1: ProcessarPagamento (tentativa 3)
    "StepFailed",                # Step 1: ProcessarPagamento (esgotou tentativas)
    "SagaCompensating",          # Saga entra em compensação
    "StepCompensationStarted",   # Step 0: LiberarEstoque
    "StepCompensated",           # Step 0: LiberarEstoque concluído
    "SagaCompensated",           # Saga concluída em estado consistente
]

OK  = "✅"
ERR = "❌"
INFO = "ℹ️ "


def check(condition: bool, label: str, detail: str = ""):
    if condition:
        print(f"  {OK} {label}")
    else:
        print(f"  {ERR} {label}" + (f": {detail}" if detail else ""))
        sys.exit(1)


# ---------------------------------------------------------------------------
# Validações
# ---------------------------------------------------------------------------

async def criar_saga_com_falha(client: httpx.AsyncClient, order_id: str) -> dict:
    # Valor > 9999.99 forçará recusa no worker de Payment
    payload = {
        "order_id": order_id,
        "customer_id": "cust-verify-comp",
        "items": [
            {"sku": "PROD-EXPENSIVE", "quantity": 1, "unit_price": 15000.00},
        ],
        "total_amount": 15000.00,
        "shipping_address": "Av. Rollback, 404 - SP",
        "payment_method": "credit_card",
    }
    res = await client.post("/sagas", json=payload)
    check(res.status_code == 202, f"POST /sagas → 202 Accepted (order_id={order_id})",
          f"status={res.status_code} body={res.text[:200]}")
    data = res.json()
    check("saga_id" in data, "Resposta contém 'saga_id'", str(data))
    check(data["order_id"] == order_id, "order_id na resposta bate com o enviado")
    check(data["status"] in ("STARTED", "RUNNING"),
          f"Status inicial é STARTED ou RUNNING (obtido: {data['status']})")
    return data


async def aguardar_compensated(client: httpx.AsyncClient, saga_id: str) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT_S
    tentativas = 0
    while time.monotonic() < deadline:
        tentativas += 1
        res = await client.get(f"/sagas/{saga_id}")
        if res.status_code == 200:
            detail = res.json()
            if detail["status"] == "COMPENSATED":
                elapsed = POLL_TIMEOUT_S - (deadline - time.monotonic())
                print(f"  {OK} Saga COMPENSATED em ~{elapsed:.2f}s "
                      f"(duration_ms={detail.get('duration_ms')}, tentativas de poll={tentativas})")
                return detail
            if detail["status"] in ("COMPLETED", "FAILED"):
                check(False, f"Saga terminou com status inesperado: {detail['status']} (esperado: COMPENSATED)")
        await asyncio.sleep(POLL_INTERVAL_S)

    check(False, f"Timeout: Saga não atingiu COMPENSATED em {POLL_TIMEOUT_S}s")


def validar_detalhe_compensacao(detail: dict, order_id: str):
    check(detail["status"] == "COMPENSATED",
          "Saga status == COMPENSATED", detail["status"])
    check(detail["order_id"] == order_id,
          "order_id correto", detail["order_id"])
    check(detail["completed_at"] is not None,
          "completed_at preenchido")
    check(detail["duration_ms"] is not None and detail["duration_ms"] >= 0,
          f"duration_ms calculado ({detail.get('duration_ms')}ms)")
    check(detail["started_at"] is not None,
          "started_at preenchido")

    steps = detail.get("steps", [])
    check(len(steps) == 4, "Número total de steps == 4", str(len(steps)))

    # Step 0: ReservarEstoque -> completou na ida e foi COMPENSATED na volta
    step_0 = steps[0]
    check(step_0["name"] == "ReservarEstoque", "Step 0 é ReservarEstoque")
    check(step_0["status"] == "COMPENSATED",
          "Step 0 (ReservarEstoque) → status COMPENSATED", step_0["status"])
    check(step_0["started_at"] is not None, "Step 0 → started_at preenchido")
    check(step_0["completed_at"] is not None, "Step 0 → completed_at preenchido")

    # Step 1: ProcessarPagamento -> FALHOU (recusado por limite de crédito)
    step_1 = steps[1]
    check(step_1["name"] == "ProcessarPagamento", "Step 1 é ProcessarPagamento")
    check(step_1["status"] == "FAILED",
          "Step 1 (ProcessarPagamento) → status FAILED", step_1["status"])
    check(step_1["attempts"] == 3,
          f"Step 1 esgotou 3 tentativas (attempts={step_1.get('attempts')})")
    check("limite de crédito" in (step_1.get("error_message") or "").lower(),
          f"Step 1 contém motivo da recusa ({step_1.get('error_message')})")

    # Step 2: DespacharPedido -> PENDING (nunca iniciado)
    step_2 = steps[2]
    check(step_2["name"] == "DespacharPedido", "Step 2 é DespacharPedido")
    check(step_2["status"] == "PENDING",
          "Step 2 (DespacharPedido) → status PENDING", step_2["status"])
    check(step_2["attempts"] == 0, "Step 2 attempts == 0")

    # Step 3: NotificarCliente -> PENDING (nunca iniciado)
    step_3 = steps[3]
    check(step_3["name"] == "NotificarCliente", "Step 3 é NotificarCliente")
    check(step_3["status"] == "PENDING",
          "Step 3 (NotificarCliente) → status PENDING", step_3["status"])
    check(step_3["attempts"] == 0, "Step 3 attempts == 0")


async def validar_timeline_compensacao(client: httpx.AsyncClient, saga_id: str):
    res = await client.get(f"/sagas/{saga_id}/timeline")
    check(res.status_code == 200,
          f"GET /sagas/{saga_id}/timeline → 200 OK", res.text[:200])
    timeline = res.json()

    total = timeline.get("total_events", 0)
    expected_total = len(EXPECTED_EVENT_TYPES)
    check(total == expected_total,
          f"total_events == {expected_total} eventos no timeline",
          f"obtido={total}")

    eventos = timeline.get("events", [])
    tipos_obtidos = [e["event_type"] for e in eventos]

    check(tipos_obtidos == EXPECTED_EVENT_TYPES,
          "Sequência cronológica canônica de eventos correta",
          f"\nEsperado: {EXPECTED_EVENT_TYPES}\nObtido:   {tipos_obtidos}")

    # Validações semânticas dos eventos
    ev_step_failed = next(e for e in eventos if e["event_type"] == "StepFailed")
    check(ev_step_failed.get("step") == "ProcessarPagamento",
          "StepFailed associado a 'ProcessarPagamento'")
    check("limite de crédito" in str(ev_step_failed.get("payload", {})).lower(),
          "StepFailed.payload descreve motivo da falha")

    ev_saga_comp = next(e for e in eventos if e["event_type"] == "SagaCompensating")
    check(ev_saga_comp.get("step") is None,
          "SagaCompensating não possui step vinculado")

    ev_comp_start = next(e for e in eventos if e["event_type"] == "StepCompensationStarted")
    check(ev_comp_start.get("step") == "ReservarEstoque",
          "StepCompensationStarted associado ao step compensado ('ReservarEstoque')")
    check(ev_comp_start.get("payload", {}).get("command_type") == "LiberarEstoque",
          "StepCompensationStarted.payload.command_type == 'LiberarEstoque'")
    check(ev_comp_start.get("payload", {}).get("service") == "inventory",
          "StepCompensationStarted.payload.service == 'inventory'")

    ev_comp_done = next(e for e in eventos if e["event_type"] == "StepCompensated")
    check(ev_comp_done.get("step") == "ReservarEstoque",
          "StepCompensated associado a 'ReservarEstoque'")

    ev_saga_done = next(e for e in eventos if e["event_type"] == "SagaCompensated")
    check(ev_saga_done.get("step") is None,
          "SagaCompensated não possui step vinculado")


async def validar_idempotencia(client: httpx.AsyncClient, order_id: str, saga_id_original: str):
    # Segunda chamada com mesmo order_id deve devolver a saga já compensada
    payload = {
        "order_id": order_id,
        "customer_id": "cust-outro",
        "items": [{"sku": "PROD-EXPENSIVE", "quantity": 1, "unit_price": 15000.00}],
        "total_amount": 15000.00,
        "shipping_address": "Rua Repetida",
        "payment_method": "credit_card",
    }
    res = await client.post("/sagas", json=payload)
    check(res.status_code == 202,
          "Idempotência: segunda chamada → 202 Accepted", res.text[:200])
    data = res.json()
    check(data["saga_id"] == saga_id_original,
          f"Idempotência: mesmo saga_id retornado ({data['saga_id']})")
    check(data["status"] == "COMPENSATED",
          f"Idempotência: status retornado é COMPENSATED ({data['status']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(base_url: str):
    print(f"🚀 Validação de Compensação / Rollback Distribuído (Card 4.3)")
    print(f"   Base URL : {base_url}")
    print(f"   Timeout  : {POLL_TIMEOUT_S}s\n")

    order_id = f"comp-{uuid.uuid4().hex[:8]}"

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        # 1. Health check rápido
        res = await client.get("/health")
        check(res.status_code == 200, "GET /health → 200 OK", res.text)
        print()

        # 2. Criar Saga com valor acima do limite (R$ 15.000,00)
        print("── Etapa 1: Criar Saga com Falha no Pagamento ──────────────")
        created = await criar_saga_com_falha(client, order_id)
        saga_id = created["saga_id"]
        print()

        # 3. Aguardar COMPENSATED
        print("── Etapa 2: Aguardar Rollback (Saga COMPENSATED) ───────────")
        detail = await aguardar_compensated(client, saga_id)
        print()

        # 4. Validar detalhe da Saga
        print("── Etapa 3: Validar Detalhes dos Steps e Status ────────────")
        validar_detalhe_compensacao(detail, order_id)
        print()

        # 5. Validar timeline
        print("── Etapa 4: Validar Linha do Tempo e Audit Trail ───────────")
        await validar_timeline_compensacao(client, saga_id)
        print()

        # 6. Idempotência
        print("── Etapa 5: Validar Idempotência ───────────────────────────")
        await validar_idempotencia(client, order_id, saga_id)
        print()

    print("=" * 60)
    print(f"🎉 Card 4.3 — Compensação validada com sucesso!")
    print(f"   Saga ID  : {saga_id}")
    print(f"   Order ID : {order_id}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Valida o fluxo de compensação do Saga Orchestrator")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8090",
        help="URL base da API do orquestrador (padrão: http://localhost:8090)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.base_url))

