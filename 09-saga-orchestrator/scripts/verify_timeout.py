"""
verify_timeout.py — Validação de Timeout Configurável por Step End-to-End (Card 5.3)

Roteiro de Validação:
  1. POST /sagas com order_id terminando em "88" (ex: ORD-TIMEOUT-XXXX88).
     - Step 0 (ReservarEstoque): executa e completa com sucesso.
     - Step 1 (ProcessarPagamento): executa e completa com sucesso.
     - Step 2 (DespacharPedido): enviado para shipping worker, que detecta final "88"
       e simula atraso excessivo (sleep 60s), não respondendo a tempo.
  2. Watchdog de Timeout:
     - Após STEP_TIMEOUT_SECONDS (5s configurado no compose), o watchdog dispara handle_timeout.
     - Step 2 é marcado como FAILED com razão TIMEOUT.
     - Eventos StepTimeout e StepFailed são gravados na timeline.
  3. Compensação em Ordem Reversa (LIFO):
     - Saga entra em COMPENSATING.
     - Step 1 (ProcessarPagamento) é desfeito via EstornarPagamento -> COMPENSATED.
     - Step 0 (ReservarEstoque) é desfeito via LiberarEstoque -> COMPENSATED.
     - Step 3 (NotificarCliente) nunca é executado -> permanece PENDING.
     - Saga atinge status final COMPENSATED.
  4. Validação da Linha do Tempo (timeline):
     - 14 eventos canônicos na ordem cronológica exata.
     - Metadados semânticos de StepTimeout e StepFailed validados.
  5. Validação de Idempotência:
     - POST subsequente com o mesmo order_id retorna a Saga existente sem duplicar execução.

Uso:
  python3 scripts/verify_timeout.py
  python3 scripts/verify_timeout.py --base-url http://localhost:8090
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
POLL_INTERVAL_S = 0.5   # intervalo de polling
POLL_TIMEOUT_S  = 30    # tempo máximo aguardando COMPENSATED (timeout 5s + compensações ~2s)

EXPECTED_EVENT_TYPES = [
    "SagaStarted",
    "StepStarted",               # Step 0: ReservarEstoque
    "StepCompleted",             # Step 0: ReservarEstoque
    "StepStarted",               # Step 1: ProcessarPagamento
    "StepCompleted",             # Step 1: ProcessarPagamento
    "StepStarted",               # Step 2: DespacharPedido (inicia execução)
    "StepTimeout",               # Step 2: DespacharPedido (watchdog expira)
    "StepFailed",                # Step 2: DespacharPedido (falha por timeout)
    "SagaCompensating",          # Saga inicia rollback ordenado
    "StepCompensationStarted",   # Step 1: EstornarPagamento
    "StepCompensated",           # Step 1: EstornarPagamento concluído
    "StepCompensationStarted",   # Step 0: LiberarEstoque
    "StepCompensated",           # Step 0: LiberarEstoque concluído
    "SagaCompensated",           # Saga restaurada para estado consistente
]

OK   = "✅"
ERR  = "❌"
INFO = "ℹ️ "


def check(condition: bool, label: str, detail: str = ""):
    if condition:
        print(f"  {OK} {label}")
    else:
        print(f"  {ERR} {label}" + (f": {detail}" if detail else ""))
        sys.exit(1)


# ---------------------------------------------------------------------------
# Operações de Validação
# ---------------------------------------------------------------------------

async def criar_saga_com_timeout(client: httpx.AsyncClient, order_id: str) -> dict:
    payload = {
        "order_id": order_id,
        "customer_id": "cust-verify-timeout",
        "items": [
            {"sku": "PROD-TIMEOUT-ITEM", "quantity": 1, "unit_price": 250.00},
        ],
        "total_amount": 250.00,
        "shipping_address": "Av. do Timeout, 88 - SP",
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


async def aguardar_compensated_por_timeout(client: httpx.AsyncClient, saga_id: str) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT_S
    tentativas = 0
    t0 = time.monotonic()
    print(f"\n{INFO} Aguardando disparo do timeout (5s) e compensação reversa...")

    while time.monotonic() < deadline:
        tentativas += 1
        res = await client.get(f"/sagas/{saga_id}")
        if res.status_code == 200:
            detail = res.json()
            status = detail.get("status")
            current = detail.get("current_step")
            elapsed = time.monotonic() - t0

            # Log de progresso a cada segundo aproximadamente
            if tentativas % 2 == 1:
                print(f"     [+{elapsed:.1f}s] status={status:<14} current_step={str(current):<20}")

            if status == "COMPENSATED":
                print(f"  {OK} Saga COMPENSATED alcançado em {elapsed:.2f}s "
                      f"(tentativas de poll: {tentativas})")
                return detail
            if status in ("COMPLETED", "FAILED"):
                check(False, f"Saga terminou com status inesperado: {status} (esperado: COMPENSATED)")
        await asyncio.sleep(POLL_INTERVAL_S)

    check(False, f"Timeout de polling: Saga não atingiu COMPENSATED em {POLL_TIMEOUT_S}s")


def validar_detalhes_saga_timeout(detail: dict, order_id: str):
    check(detail["status"] == "COMPENSATED",
          "Saga status == COMPENSATED", detail["status"])
    check(detail["order_id"] == order_id,
          "order_id correto", detail["order_id"])
    check(detail["completed_at"] is not None,
          "completed_at preenchido")
    check(detail["duration_ms"] is not None and detail["duration_ms"] > 0,
          f"duration_ms calculado ({detail.get('duration_ms')}ms)")
    check(detail["started_at"] is not None,
          "started_at preenchido")

    steps = detail.get("steps", [])
    check(len(steps) == 4, "Total de 4 steps no workflow", str(len(steps)))

    # Step 0: ReservarEstoque -> completou na ida e foi COMPENSATED na volta
    step_0 = steps[0]
    check(step_0["name"] == "ReservarEstoque", "Step 0 é ReservarEstoque")
    check(step_0["status"] == "COMPENSATED",
          "Step 0 (ReservarEstoque) → COMPENSATED", step_0["status"])
    check(step_0["started_at"] is not None, "Step 0 started_at preenchido")
    check(step_0["completed_at"] is not None, "Step 0 completed_at preenchido")

    # Step 1: ProcessarPagamento -> completou na ida e foi COMPENSATED na volta
    step_1 = steps[1]
    check(step_1["name"] == "ProcessarPagamento", "Step 1 é ProcessarPagamento")
    check(step_1["status"] == "COMPENSATED",
          "Step 1 (ProcessarPagamento) → COMPENSATED", step_1["status"])
    check(step_1["started_at"] is not None, "Step 1 started_at preenchido")
    check(step_1["completed_at"] is not None, "Step 1 completed_at preenchido")

    # Step 2: DespacharPedido -> FALHOU por timeout (worker dormiu 60s)
    step_2 = steps[2]
    check(step_2["name"] == "DespacharPedido", "Step 2 é DespacharPedido")
    check(step_2["status"] == "FAILED",
          "Step 2 (DespacharPedido) → FAILED", step_2["status"])
    check("timeout" in (step_2.get("error_message") or "").lower(),
          f"Step 2 error_message descreve timeout ({step_2.get('error_message')})")

    # Step 3: NotificarCliente -> PENDING (nunca iniciado)
    step_3 = steps[3]
    check(step_3["name"] == "NotificarCliente", "Step 3 é NotificarCliente")
    check(step_3["status"] == "PENDING",
          "Step 3 (NotificarCliente) → PENDING", step_3["status"])
    check(step_3["attempts"] == 0, "Step 3 attempts == 0")


async def validar_timeline_timeout(client: httpx.AsyncClient, saga_id: str):
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
          "Sequência canônica completa de eventos correta",
          f"\nEsperado: {EXPECTED_EVENT_TYPES}\nObtido:   {tipos_obtidos}")

    # Validação do evento StepTimeout
    ev_timeout = next(e for e in eventos if e["event_type"] == "StepTimeout")
    check(ev_timeout.get("step") == "DespacharPedido",
          "Evento StepTimeout associado a 'DespacharPedido'")
    p_timeout = ev_timeout.get("payload", {})
    check(p_timeout.get("step_index") == 2,
          "StepTimeout.payload step_index == 2", str(p_timeout))
    check("timeout_seconds" in p_timeout and p_timeout["timeout_seconds"] > 0,
          f"StepTimeout.payload timeout_seconds registrado ({p_timeout.get('timeout_seconds')}s)")

    # Validação do evento StepFailed
    ev_failed = next(e for e in eventos if e["event_type"] == "StepFailed")
    check(ev_failed.get("step") == "DespacharPedido",
          "Evento StepFailed associado a 'DespacharPedido'")
    check(ev_failed.get("payload", {}).get("reason") == "TIMEOUT",
          "StepFailed.payload reason == 'TIMEOUT'")

    # Validação da ordem de compensação LIFO (DespacharPedido falhou -> EstornarPagamento -> LiberarEstoque)
    comp_events = [e for e in eventos if e["event_type"] == "StepCompensationStarted"]
    check(len(comp_events) == 2, "Exatamente 2 steps compensados (steps 1 e 0)")
    check(comp_events[0].get("step") == "ProcessarPagamento",
          "1º step compensado é ProcessarPagamento (rollback reverso LIFO)")
    check(comp_events[0].get("payload", {}).get("command_type") == "EstornarPagamento",
          "Comando de compensação do pagamento é 'EstornarPagamento'")
    check(comp_events[1].get("step") == "ReservarEstoque",
          "2º step compensado é ReservarEstoque")
    check(comp_events[1].get("payload", {}).get("command_type") == "LiberarEstoque",
          "Comando de compensação do estoque é 'LiberarEstoque'")

    # Evento final SagaCompensated
    ev_saga_comp = eventos[-1]
    check(ev_saga_comp["event_type"] == "SagaCompensated",
          "Último evento é SagaCompensated")
    check(ev_saga_comp.get("step") is None,
          "SagaCompensated sem step vinculado")


async def validar_idempotencia_timeout(client: httpx.AsyncClient, order_id: str, saga_id: str):
    payload = {
        "order_id": order_id,
        "customer_id": "cust-verify-timeout-dup",
        "items": [{"sku": "PROD-TIMEOUT-ITEM", "quantity": 1, "unit_price": 250.00}],
        "total_amount": 250.00,
        "shipping_address": "Av. do Timeout, 88 - SP",
        "payment_method": "credit_card",
    }
    res = await client.post("/sagas", json=payload)
    check(res.status_code in (200, 202),
          f"Reenvio com mesmo order_id → 200/202 (idempotente)", f"status={res.status_code}")
    data = res.json()
    check(data.get("saga_id") == saga_id,
          "saga_id retornado é idêntico ao da primeira chamada",
          f"{data.get('saga_id')} != {saga_id}")
    check(data.get("status") == "COMPENSATED",
          "Status da Saga existente preservado em COMPENSATED")


# ---------------------------------------------------------------------------
# Fluxo Principal
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="Validação de Timeout no Step End-to-End (Card 5.3)")
    parser.add_argument("--base-url", default="http://localhost:8090",
                        help="URL base do Orchestrator (padrão: http://localhost:8090)")
    args = parser.parse_args()

    # O order_id DEVE terminar em "88" para acionar a simulação de timeout no worker de shipping
    unique_suffix = uuid.uuid4().hex[:6].upper()
    order_id = f"ORD-TIME-{unique_suffix}88"

    print("=" * 70)
    print(" SAGA ORCHESTRATOR — VALIDAÇÃO DE TIMEOUT NO STEP (CARD 5.3)")
    print(f" Target: {args.base_url}")
    print(f" Order ID: {order_id} (termina em '88' -> timeout no shipping)")
    print("=" * 70)

    async with httpx.AsyncClient(base_url=args.base_url, timeout=10.0) as client:
        # 1. Healthcheck
        print(f"\n[1/5] Verificando integridade da API...")
        try:
            res = await client.get("/health")
            check(res.status_code == 200 and res.json().get("status") in ("ok", "healthy"),
                  "Orchestrator está ativo e saudável")
        except Exception as e:
            check(False, "Conexão com Orchestrator falhou", str(e))

        # 2. Criação da Saga com order_id terminando em "88"
        print(f"\n[2/5] Criando Saga com order_id terminando em '88'...")
        saga_data = await criar_saga_com_timeout(client, order_id)
        saga_id = saga_data["saga_id"]
        print(f"      Saga ID: {saga_id}")

        # 3. Aguardar timeout no step 2 e compensação dos steps anteriores
        print(f"\n[3/5] Aguardando timeout do shipping (STEP_TIMEOUT_SECONDS=5s) e compensação...")
        detail = await aguardar_compensated_por_timeout(client, saga_id)
        validar_detalhes_saga_timeout(detail, order_id)

        # 4. Validação da timeline e sequência cronológica de eventos
        print(f"\n[4/5] Validando timeline e eventos StepTimeout / Rollback LIFO...")
        await validar_timeline_timeout(client, saga_id)

        # 5. Idempotência por order_id
        print(f"\n[5/5] Testando idempotência (reenvio do mesmo order_id)...")
        await validar_idempotencia_timeout(client, order_id, saga_id)

    print("\n" + "=" * 70)
    print(f" {OK} CARD 5.3 VALIDADO COM SUCESSO!")
    print(f"     - Timeout do step detectado pontualmente pelo watchdog")
    print(f"     - Eventos StepTimeout e StepFailed registrados com precisão")
    print(f"     - Rollback reverso (LIFO) executado com sucesso: Step 1 -> Step 0")
    print(f"     - Saga finalizada em estado consistente COMPENSATED")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
