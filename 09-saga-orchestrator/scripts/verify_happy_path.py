"""
verify_happy_path.py — Validação do Happy Path End-to-End (Card 3.4)

Roteiro:
  1. POST /sagas → cria uma nova Saga com order_id único
  2. Polling com timeout de 30s até status == COMPLETED
  3. Valida que todos os 4 steps estão COMPLETED
  4. Valida os campos de cada step (attempts, started_at, completed_at)
  5. Consulta o timeline e valida os 10 eventos esperados
  6. Valida a sequência correta de event_types no timeline
  7. Testa idempotência: segunda chamada com mesmo order_id retorna a saga existente

Uso:
  python3 scripts/verify_happy_path.py
  python3 scripts/verify_happy_path.py --base-url http://localhost:8090
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
POLL_TIMEOUT_S  = 30    # tempo máximo aguardando COMPLETED
EXPECTED_STEPS  = 4     # passos do workflow ProcessarPedido
# Sequência canônica de eventos para happy path com 4 steps:
# SagaStarted + (StepStarted + StepCompleted) x4 + SagaCompleted
EXPECTED_EVENT_TYPES = (
    ["SagaStarted"]
    + ["StepStarted", "StepCompleted"] * EXPECTED_STEPS
    + ["SagaCompleted"]
)
EXPECTED_STEP_NAMES = [
    "ReservarEstoque",
    "ProcessarPagamento",
    "DespacharPedido",
    "NotificarCliente",
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

async def criar_saga(client: httpx.AsyncClient, order_id: str) -> dict:
    payload = {
        "order_id": order_id,
        "customer_id": "cust-verify-hp",
        "items": [
            {"sku": "PROD-HP", "quantity": 2, "unit_price": 49.90},
        ],
        "total_amount": 99.80,
        "shipping_address": "Av. Saga, 100 - SP",
        "payment_method": "credit_card",
    }
    res = await client.post("/sagas", json=payload)
    check(res.status_code == 202, f"POST /sagas → 202 Accepted (order_id={order_id})",
          f"status={res.status_code} body={res.text[:200]}")
    data = res.json()
    check("saga_id" in data,      "Resposta contém 'saga_id'",      str(data))
    check(data["order_id"] == order_id, "order_id na resposta bate com o enviado")
    check(data["status"] in ("STARTED", "RUNNING"),
          f"Status inicial é STARTED ou RUNNING (obtido: {data['status']})")
    return data


async def aguardar_completed(client: httpx.AsyncClient, saga_id: str) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT_S
    tentativas = 0
    while time.monotonic() < deadline:
        tentativas += 1
        res = await client.get(f"/sagas/{saga_id}")
        if res.status_code == 200:
            detail = res.json()
            if detail["status"] == "COMPLETED":
                elapsed = POLL_TIMEOUT_S - (deadline - time.monotonic())
                print(f"  {OK} Saga COMPLETED em ~{elapsed:.2f}s "
                      f"(duration_ms={detail.get('duration_ms')}, tentativas de poll={tentativas})")
                return detail
            if detail["status"] in ("FAILED", "COMPENSATED", "COMPENSATING"):
                check(False, f"Saga terminou com status inesperado: {detail['status']}")
        await asyncio.sleep(POLL_INTERVAL_S)

    check(False, f"Timeout: Saga não atingiu COMPLETED em {POLL_TIMEOUT_S}s")


def validar_detalhe(detail: dict, order_id: str):
    check(detail["status"] == "COMPLETED",
          "status == COMPLETED", detail["status"])
    check(detail["order_id"] == order_id,
          "order_id correto", detail["order_id"])
    check(detail["completed_at"] is not None,
          "completed_at preenchido")
    check(detail["duration_ms"] is not None and detail["duration_ms"] >= 0,
          f"duration_ms calculado ({detail.get('duration_ms')}ms)")
    check(detail["started_at"] is not None,
          "started_at preenchido")

    steps = detail.get("steps", [])
    check(len(steps) == EXPECTED_STEPS,
          f"Número de steps == {EXPECTED_STEPS}", str(len(steps)))

    # Verifica cada step em ordem
    step_names = [s["name"] for s in steps]
    check(step_names == EXPECTED_STEP_NAMES,
          f"Nomes dos steps na ordem correta",
          f"obtido={step_names}")

    for i, step in enumerate(steps):
        nome = step["name"]
        check(step["status"] == "COMPLETED",
              f"Step [{i}] {nome} → status COMPLETED", step["status"])
        check(step["attempts"] >= 1,
              f"Step [{i}] {nome} → attempts >= 1", str(step["attempts"]))
        check(step["started_at"] is not None,
              f"Step [{i}] {nome} → started_at preenchido")
        check(step["completed_at"] is not None,
              f"Step [{i}] {nome} → completed_at preenchido")
        check(step["error_message"] is None,
              f"Step [{i}] {nome} → sem error_message", str(step["error_message"]))


async def validar_timeline(client: httpx.AsyncClient, saga_id: str):
    res = await client.get(f"/sagas/{saga_id}/timeline")
    check(res.status_code == 200,
          f"GET /sagas/{saga_id}/timeline → 200 OK", res.text[:200])
    timeline = res.json()

    total = timeline.get("total_events", 0)
    expected_total = len(EXPECTED_EVENT_TYPES)
    check(total == expected_total,
          f"total_events == {expected_total} (SagaStarted + 4×StepStarted + 4×StepCompleted + SagaCompleted)",
          f"obtido={total}")

    eventos = timeline.get("events", [])
    tipos_obtidos = [e["event_type"] for e in eventos]

    check(tipos_obtidos == EXPECTED_EVENT_TYPES,
          "Sequência de event_types correta",
          f"\nEsperado: {EXPECTED_EVENT_TYPES}\nObtido:   {tipos_obtidos}")

    # Valida que StepStarted/StepCompleted têm o campo 'step' preenchido
    for ev in eventos:
        if ev["event_type"] in ("StepStarted", "StepCompleted"):
            check(ev.get("step") is not None,
                  f"Evento '{ev['event_type']}' tem campo 'step' preenchido ({ev.get('step')})")

    # Valida que SagaStarted e SagaCompleted NÃO têm step vinculado
    saga_started = next(e for e in eventos if e["event_type"] == "SagaStarted")
    check(saga_started.get("step") is None,
          "SagaStarted não tem 'step' vinculado")

    saga_completed = next(e for e in eventos if e["event_type"] == "SagaCompleted")
    check(saga_completed.get("step") is None,
          "SagaCompleted não tem 'step' vinculado")
    check(saga_completed["payload"].get("order_id") is not None,
          "SagaCompleted.payload contém order_id")


async def validar_idempotencia(client: httpx.AsyncClient, order_id: str, saga_id_original: str):
    # Segunda chamada com mesmo order_id deve devolver a saga já existente
    payload = {
        "order_id": order_id,
        "customer_id": "cust-outro",
        "items": [{"sku": "X", "quantity": 1, "unit_price": 1.0}],
        "total_amount": 1.0,
        "shipping_address": "Rua Y",
        "payment_method": "pix",
    }
    res = await client.post("/sagas", json=payload)
    check(res.status_code == 202,
          "Idempotência: segunda chamada → 202 Accepted", res.text[:200])
    data = res.json()
    check(data["saga_id"] == saga_id_original,
          f"Idempotência: mesmo saga_id retornado ({data['saga_id']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(base_url: str):
    print(f"🚀 Validação do Happy Path End-to-End (Card 3.4)")
    print(f"   Base URL : {base_url}")
    print(f"   Timeout  : {POLL_TIMEOUT_S}s\n")

    order_id = f"hp-{uuid.uuid4().hex[:8]}"

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        # 1. Health check rápido
        res = await client.get("/health")
        check(res.status_code == 200, "GET /health → 200 OK", res.text)
        print()

        # 2. Criar Saga
        print("── Etapa 1: Criar Saga ─────────────────────────────────────")
        created = await criar_saga(client, order_id)
        saga_id = created["saga_id"]
        print()

        # 3. Aguardar COMPLETED
        print("── Etapa 2: Aguardar Saga COMPLETED ────────────────────────")
        detail = await aguardar_completed(client, saga_id)
        print()

        # 4. Validar detalhe da Saga
        print("── Etapa 3: Validar GET /sagas/{saga_id} ───────────────────")
        validar_detalhe(detail, order_id)
        print()

        # 5. Validar timeline
        print("── Etapa 4: Validar GET /sagas/{saga_id}/timeline ──────────")
        await validar_timeline(client, saga_id)
        print()

        # 6. Idempotência
        print("── Etapa 5: Validar Idempotência ───────────────────────────")
        await validar_idempotencia(client, order_id, saga_id)
        print()

    print("=" * 60)
    print(f"🎉 Card 3.4 — Happy Path validado com sucesso!")
    print(f"   Saga ID  : {saga_id}")
    print(f"   Order ID : {order_id}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Valida o happy path do Saga Orchestrator")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8090",
        help="URL base da API do orquestrador (padrão: http://localhost:8090)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.base_url))

