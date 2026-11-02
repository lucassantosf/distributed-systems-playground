"""
verify_all_scenarios.py — Validação dos 6 Cenários Determinísticos Completos (Card 8.1)

Executa os 6 cenários da Tabela de Falhas em sequência e imprime um relatório consolidado:
  1. ✅ Happy Path: total_amount <= 9999.99 sem SKUs especiais -> Todos os steps completam -> Saga COMPLETED.
  2. 💳 Pagamento Recusado: total_amount > 9999.99 -> Payment falha -> Rollback LIFO -> Saga COMPENSATED.
  3. 📦 Estoque Indisponível: SKU contendo "ESGOTADO" -> Inventory falha no step 0 -> Nenhum step completado -> Saga COMPENSATED.
  4. ⏱️ Timeout de Despacho: order_id terminando em "88" -> Shipping worker não responde -> Watchdog timeout -> Rollback -> Saga COMPENSATED.
  5. 🔁 Falha Transitória: order_id terminando em "77" -> Payment falha nas tentativas 1 e 2, sucede na 3ª -> Saga COMPLETED.
  6. 💥 Falha na Compensação: order_id terminando em "66" com recusa de pagamento -> Rollback no Inventory falha -> DLQ alert -> Saga FAILED.

Uso:
  python3 scripts/verify_all_scenarios.py
  python3 scripts/verify_all_scenarios.py --base-url http://localhost:8090
"""
import argparse
import asyncio
import os
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

try:
    import httpx
except ImportError:
    httpx = None

POLL_INTERVAL_S = 0.5
POLL_TIMEOUT_S = 35  # suficiente para retries com backoff e timeout de shipping

OK = "✅"
ERR = "❌"
WARN = "⚠️"
INFO = "ℹ️ "


class ScenarioResult:
    def __init__(self, name: str, code: str):
        self.name = name
        self.code = code
        self.passed = False
        self.order_id = ""
        self.saga_id = ""
        self.final_status = ""
        self.duration_s = 0.0
        self.details: List[str] = []
        self.error: Optional[str] = None


async def aguardar_status_final(
    client: httpx.AsyncClient,
    saga_id: str,
    target_statuses: Tuple[str, ...],
    timeout_s: float = POLL_TIMEOUT_S,
) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last_status = "UNKNOWN"
    last_data = {}

    while time.monotonic() < deadline:
        res = await client.get(f"/sagas/{saga_id}")
        if res.status_code == 200:
            last_data = res.json()
            last_status = last_data.get("status", "UNKNOWN")
            if last_status in target_statuses:
                return last_data
            # Se for um status terminal diferente do esperado, encerra mais cedo
            if last_status in ("COMPLETED", "COMPENSATED", "FAILED") and last_status not in target_statuses:
                raise RuntimeError(
                    f"Saga atingiu status terminal '{last_status}', mas esperava um de {target_statuses}"
                )
        await asyncio.sleep(POLL_INTERVAL_S)

    raise TimeoutError(
        f"Timeout ({timeout_s}s) aguardando status {target_statuses}. Último status: '{last_status}'"
    )


async def executar_cenario_1_happy_path(client: httpx.AsyncClient) -> ScenarioResult:
    res = ScenarioResult("Happy Path", "1-HAPPY-PATH")
    start_time = time.monotonic()
    order_id = f"ORD-SCENARIO-HP-{uuid.uuid4().hex[:6]}"
    res.order_id = order_id

    payload = {
        "order_id": order_id,
        "customer_id": "cust-scen-1",
        "items": [{"sku": "PROD-A", "quantity": 2, "unit_price": 50.0}],
        "total_amount": 100.0,
        "shipping_address": "Rua 1, Centro - SP",
        "payment_method": "credit_card",
    }

    create_res = await client.post("/sagas", json=payload)
    if create_res.status_code != 202:
        res.error = f"POST /sagas retornou {create_res.status_code}: {create_res.text}"
        return res

    res.saga_id = create_res.json()["saga_id"]
    detail = await aguardar_status_final(client, res.saga_id, ("COMPLETED",))
    res.final_status = detail.get("status", "")

    # Validações dos steps
    steps = detail.get("steps", [])
    if len(steps) != 4:
        raise ValueError(f"Esperado 4 steps, obteve {len(steps)}")
    for s in steps:
        if s["status"] != "COMPLETED":
            raise ValueError(f"Step {s['name']} com status {s['status']} (esperado: COMPLETED)")

    res.details.append("Todos os 4 steps concluídos com sucesso (COMPLETED)")
    res.passed = True
    res.duration_s = time.monotonic() - start_time
    return res


async def executar_cenario_2_pagamento_recusado(client: httpx.AsyncClient) -> ScenarioResult:
    res = ScenarioResult("Pagamento Recusado", "2-PAY-REFUSED")
    start_time = time.monotonic()
    order_id = f"ORD-SCENARIO-PAY-{uuid.uuid4().hex[:6]}"
    res.order_id = order_id

    # total_amount > 9999.99 força recusa por limite
    payload = {
        "order_id": order_id,
        "customer_id": "cust-scen-2",
        "items": [{"sku": "PROD-EXPENSIVE", "quantity": 1, "unit_price": 12000.0}],
        "total_amount": 12000.0,
        "shipping_address": "Rua 2, Centro - SP",
        "payment_method": "credit_card",
    }

    create_res = await client.post("/sagas", json=payload)
    if create_res.status_code != 202:
        res.error = f"POST /sagas retornou {create_res.status_code}: {create_res.text}"
        return res

    res.saga_id = create_res.json()["saga_id"]
    detail = await aguardar_status_final(client, res.saga_id, ("COMPENSATED",))
    res.final_status = detail.get("status", "")

    steps = detail.get("steps", [])
    step_0 = next(s for s in steps if s["index"] == 0)
    step_1 = next(s for s in steps if s["index"] == 1)

    if step_0["status"] != "COMPENSATED":
        raise ValueError(f"Step 0 (Estoque) esperado COMPENSATED, obteve {step_0['status']}")
    if step_1["status"] != "FAILED":
        raise ValueError(f"Step 1 (Pagamento) esperado FAILED, obteve {step_1['status']}")

    res.details.append("Step 1 (Pagamento) falhou e Step 0 (Estoque) foi compensado")
    res.passed = True
    res.duration_s = time.monotonic() - start_time
    return res


async def executar_cenario_3_estoque_indisponivel(client: httpx.AsyncClient) -> ScenarioResult:
    res = ScenarioResult("Estoque Indisponível", "3-OUT-OF-STOCK")
    start_time = time.monotonic()
    order_id = f"ORD-SCENARIO-STOCK-{uuid.uuid4().hex[:6]}"
    res.order_id = order_id

    # SKU contendo ESGOTADO
    payload = {
        "order_id": order_id,
        "customer_id": "cust-scen-3",
        "items": [{"sku": "PROD-ESGOTADO-99", "quantity": 1, "unit_price": 80.0}],
        "total_amount": 80.0,
        "shipping_address": "Rua 3, Centro - SP",
        "payment_method": "credit_card",
    }

    create_res = await client.post("/sagas", json=payload)
    if create_res.status_code != 202:
        res.error = f"POST /sagas retornou {create_res.status_code}: {create_res.text}"
        return res

    res.saga_id = create_res.json()["saga_id"]
    # Falha no Step 0 sem nada a compensar transiciona para COMPENSATED
    detail = await aguardar_status_final(client, res.saga_id, ("COMPENSATED",))
    res.final_status = detail.get("status", "")

    steps = detail.get("steps", [])
    step_0 = next(s for s in steps if s["index"] == 0)
    if step_0["status"] != "FAILED":
        raise ValueError(f"Step 0 esperado FAILED, obteve {step_0['status']}")

    res.details.append("Step 0 (Estoque) falhou por produto esgotado; Saga finalizou COMPENSATED")
    res.passed = True
    res.duration_s = time.monotonic() - start_time
    return res


async def executar_cenario_4_timeout_despacho(client: httpx.AsyncClient) -> ScenarioResult:
    res = ScenarioResult("Timeout de Despacho", "4-SHIPPING-TIMEOUT")
    start_time = time.monotonic()
    # order_id terminando em 88 aciona timeout intencional no shipping worker
    order_id = f"ORD-SCENARIO-{uuid.uuid4().hex[:4]}88"
    res.order_id = order_id

    payload = {
        "order_id": order_id,
        "customer_id": "cust-scen-4",
        "items": [{"sku": "PROD-NORMAL", "quantity": 1, "unit_price": 150.0}],
        "total_amount": 150.0,
        "shipping_address": "Rua 4, Centro - SP",
        "payment_method": "credit_card",
    }

    create_res = await client.post("/sagas", json=payload)
    if create_res.status_code != 202:
        res.error = f"POST /sagas retornou {create_res.status_code}: {create_res.text}"
        return res

    res.saga_id = create_res.json()["saga_id"]
    detail = await aguardar_status_final(client, res.saga_id, ("COMPENSATED",))
    res.final_status = detail.get("status", "")

    steps = detail.get("steps", [])
    step_0 = next(s for s in steps if s["index"] == 0)
    step_1 = next(s for s in steps if s["index"] == 1)
    step_2 = next(s for s in steps if s["index"] == 2)

    if step_2["status"] != "FAILED":
        raise ValueError(f"Step 2 (Despacho) esperado FAILED por timeout, obteve {step_2['status']}")
    if step_1["status"] != "COMPENSATED":
        raise ValueError(f"Step 1 (Pagamento) esperado COMPENSATED, obteve {step_1['status']}")
    if step_0["status"] != "COMPENSATED":
        raise ValueError(f"Step 0 (Estoque) esperado COMPENSATED, obteve {step_0['status']}")

    res.details.append("Step 2 sofreu timeout; steps 1 e 0 foram compensados em ordem reversa")
    res.passed = True
    res.duration_s = time.monotonic() - start_time
    return res


async def executar_cenario_5_falha_transitoria(client: httpx.AsyncClient) -> ScenarioResult:
    res = ScenarioResult("Falha Transitória com Retry", "5-TRANSIENT-RETRY")
    start_time = time.monotonic()
    # order_id terminando em 77 falha nas tentativas 1 e 2 no payment, sucede na 3ª
    order_id = f"ORD-SCENARIO-{uuid.uuid4().hex[:4]}77"
    res.order_id = order_id

    payload = {
        "order_id": order_id,
        "customer_id": "cust-scen-5",
        "items": [{"sku": "PROD-RETRY", "quantity": 1, "unit_price": 90.0}],
        "total_amount": 90.0,
        "shipping_address": "Rua 5, Centro - SP",
        "payment_method": "credit_card",
    }

    create_res = await client.post("/sagas", json=payload)
    if create_res.status_code != 202:
        res.error = f"POST /sagas retornou {create_res.status_code}: {create_res.text}"
        return res

    res.saga_id = create_res.json()["saga_id"]
    detail = await aguardar_status_final(client, res.saga_id, ("COMPLETED",))
    res.final_status = detail.get("status", "")

    steps = detail.get("steps", [])
    step_1 = next(s for s in steps if s["index"] == 1)
    if step_1["status"] != "COMPLETED":
        raise ValueError(f"Step 1 esperado COMPLETED após retries, obteve {step_1['status']}")
    if step_1.get("attempts", 1) < 3:
        raise ValueError(f"Step 1 esperado 3 tentativas (attempts), obteve {step_1.get('attempts')}")

    res.details.append(f"Step 1 completou com sucesso na 3ª tentativa (attempts={step_1.get('attempts')})")
    res.passed = True
    res.duration_s = time.monotonic() - start_time
    return res


async def executar_cenario_6_falha_na_compensacao(client: httpx.AsyncClient) -> ScenarioResult:
    res = ScenarioResult("Falha na Compensação (DLQ)", "6-COMPENSATION-FAILED")
    start_time = time.monotonic()
    # order_id terminando em 66 com total_amount > 9999.99:
    # 1. Step 0 (ReservarEstoque) completa.
    # 2. Step 1 (ProcessarPagamento) falha por limite.
    # 3. Rollback aciona LiberarEstoque com order_id terminando em 66 -> falha fatal.
    # 4. Step 0 atinge COMPENSATING_FAILED e Saga FAILED -> alerta DLQ.
    order_id = f"ORD-SCENARIO-{uuid.uuid4().hex[:4]}66"
    res.order_id = order_id

    payload = {
        "order_id": order_id,
        "customer_id": "cust-scen-6",
        "items": [{"sku": "PROD-FATAL", "quantity": 1, "unit_price": 15000.0}],
        "total_amount": 15000.0,
        "shipping_address": "Rua 6, Centro - SP",
        "payment_method": "credit_card",
    }

    create_res = await client.post("/sagas", json=payload)
    if create_res.status_code != 202:
        res.error = f"POST /sagas retornou {create_res.status_code}: {create_res.text}"
        return res

    res.saga_id = create_res.json()["saga_id"]
    detail = await aguardar_status_final(client, res.saga_id, ("FAILED",))
    res.final_status = detail.get("status", "")

    steps = detail.get("steps", [])
    step_0 = next(s for s in steps if s["index"] == 0)
    if step_0["status"] != "COMPENSATING_FAILED":
        raise ValueError(
            f"Step 0 esperado COMPENSATING_FAILED, obteve {step_0['status']}"
        )

    res.details.append("Compensação falhou fatalmente; step marcado COMPENSATING_FAILED e Saga FAILED")
    res.passed = True
    res.duration_s = time.monotonic() - start_time
    return res


async def main():
    if httpx is None:
        print("❌ Dependência ausente: instale com 'pip install httpx'")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Validação de Todos os Cenários Determinísticos (Card 8.1)")
    parser.add_argument(
        "--base-url",
        default=os.getenv("ORCHESTRATOR_URL", "http://localhost:8090"),
        help="URL base do Saga Orchestrator",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  🚀 SAGA ORCHESTRATOR — SUÍTE DE CENÁRIOS DETERMINÍSTICOS (CARD 8.1)")
    print("=" * 70)
    print(f"  Target: {args.base_url}")
    print(f"  Total de Cenários: 6\n")

    scenarios = [
        ("Cenário 1 — Happy Path (Sucesso Completo)", executar_cenario_1_happy_path),
        ("Cenário 2 — Pagamento Recusado (Compensação Limite)", executar_cenario_2_pagamento_recusado),
        ("Cenário 3 — Estoque Indisponível (Falha Inicial)", executar_cenario_3_estoque_indisponivel),
        ("Cenário 4 — Timeout de Despacho (Watchdog Timeout)", executar_cenario_4_timeout_despacho),
        ("Cenário 5 — Falha Transitória (Retry com Sucesso na 3ª)", executar_cenario_5_falha_transitoria),
        ("Cenário 6 — Falha na Compensação (Alerta DLQ e Saga FAILED)", executar_cenario_6_falha_na_compensacao),
    ]

    results: List[ScenarioResult] = []

    async with httpx.AsyncClient(base_url=args.base_url, timeout=15.0) as client:
        # Verifica health
        try:
            h = await client.get("/health")
            if h.status_code != 200:
                print(f"❌ Orquestrador não saudável em {args.base_url}/health")
                sys.exit(1)
        except Exception as e:
            print(f"❌ Não foi possível conectar ao orquestrador em {args.base_url}: {e}")
            sys.exit(1)

        for idx, (title, func) in enumerate(scenarios, 1):
            print(f"▶️  [{idx}/6] Executando: {title}...")
            try:
                res = await func(client)
            except Exception as exc:
                res = ScenarioResult(title, f"{idx}-ERROR")
                res.error = str(exc)

            status_icon = OK if res.passed else ERR
            res_label = "PASSED" if res.passed else "FAILED"
            print(f"    {status_icon} Resultado: {res_label} ({res.duration_s:.2f}s) | Status: {res.final_status or 'N/A'}")
            if res.details:
                for d in res.details:
                    print(f"       • {d}")
            if res.error:
                print(f"       ⚠️  Erro: {res.error}")
            print()
            results.append(res)

    # Relatório Consolidado
    print("=" * 70)
    print("  📊 RELATÓRIO CONSOLIDADO DE EXECUÇÃO")
    print("=" * 70)
    print(f"{'#':<3} | {'CENÁRIO':<35} | {'STATUS':<8} | {'DURAÇÃO':<8} | {'SAGA STATUS':<12}")
    print("-" * 70)

    all_passed = True
    for i, r in enumerate(results, 1):
        status_str = "PASSED" if r.passed else "FAILED"
        if not r.passed:
            all_passed = False
        print(f"{i:<3} | {r.name:<35} | {status_str:<8} | {r.duration_s:>6.2f}s | {r.final_status:<12}")

    print("=" * 70)
    if all_passed:
        print(f"  🎉 TODOS OS 6 CENÁRIOS PASSARAM COM SUCESSO! {OK}")
        print("=" * 70 + "\n")
        sys.exit(0)
    else:
        print(f"  ❌ UM OU MAIS CENÁRIOS FALHARAM. Verifique os logs acima. {ERR}")
        print("=" * 70 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
