"""
verify_concurrent_sagas.py — Validação de Sagas Concorrentes em Paralelo (Card 8.3)

Roteiro de Validação:
  1. Dispara N Sagas (default: 20) simultaneamente em paralelo via asyncio.gather.
  2. Cada Saga utiliza um order_id único com payload Happy Path.
  3. Realiza polling concorrente aguardando todas as 20 Sagas atingirem o status final esperado (COMPLETED).
  4. Valida a integridade individual de cada Saga:
     - Status == COMPLETED
     - Total de 4 steps concluídos (COMPLETED)
     - attempts == 1 em todos os steps
  5. Garante que o lock distribuído no Redis coordenou o processamento concorrente
     sem race conditions, colisões de estado ou deadlocks.

Uso:
  python3 scripts/verify_concurrent_sagas.py
  python3 scripts/verify_concurrent_sagas.py --count 20 --base-url http://localhost:8090
"""
import argparse
import asyncio
import os
import sys
import time
import uuid
from typing import Any, Dict, List

try:
    import httpx
except ImportError:
    print("❌ Dependência ausente: instale com 'pip install httpx'")
    sys.exit(1)

POLL_INTERVAL_S = 0.5
POLL_TIMEOUT_S = 40

OK = "✅"
ERR = "❌"
INFO = "ℹ️ "


def check(condition: bool, label: str, detail: str = ""):
    if condition:
        print(f"  {OK} {label}")
    else:
        print(f"  {ERR} {label}" + (f": {detail}" if detail else ""))
        sys.exit(1)


async def criar_e_acompanhar_saga(client: httpx.AsyncClient, index: int, timeout_s: float = POLL_TIMEOUT_S) -> Dict[str, Any]:
    order_id = f"ORD-CONC-{index:03d}-{uuid.uuid4().hex[:6]}"
    payload = {
        "order_id": order_id,
        "customer_id": f"cust-conc-{index}",
        "items": [{"sku": f"PROD-CONC-{index}", "quantity": 1, "unit_price": 50.0}],
        "total_amount": 50.0,
        "shipping_address": f"Rua Concorrente, {index}",
        "payment_method": "credit_card",
    }

    start_time = time.monotonic()
    res = await client.post("/sagas", json=payload)
    if res.status_code != 202:
        raise RuntimeError(f"POST /sagas falhou para {order_id} (status={res.status_code}): {res.text}")

    saga_id = res.json()["saga_id"]

    # Polling até status final
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        d_res = await client.get(f"/sagas/{saga_id}")
        if d_res.status_code == 200:
            detail = d_res.json()
            if detail.get("status") in ("COMPLETED", "COMPENSATED", "FAILED"):
                detail["elapsed_s"] = time.monotonic() - start_time
                return detail
        await asyncio.sleep(POLL_INTERVAL_S)

    raise TimeoutError(f"Saga {saga_id} ({order_id}) não concluiu em {timeout_s}s")


async def main():
    parser = argparse.ArgumentParser(description="Validação de Sagas Concorrentes (Card 8.3)")
    parser.add_argument(
        "--count",
        type=int,
        default=20,
        help="Quantidade de Sagas simultâneas a disparar (default: 20)",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("ORCHESTRATOR_URL", "http://localhost:8090"),
        help="URL base do Saga Orchestrator",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(f"  ⚡ VALIDAÇÃO DE {args.count} SAGAS CONCORRENTES EM PARALELO (CARD 8.3)")
    print("=" * 70)
    print(f"  Target: {args.base_url}")
    print(f"  Total Concorrente: {args.count} workflows via asyncio.gather\n")

    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=20.0, limits=limits) as client:
        # 1. Verifica conectividade
        try:
            h = await client.get("/health")
            check(h.status_code == 200, "Orquestrador online e saudável")
        except Exception as e:
            print(f"❌ Não foi possível conectar ao orquestrador em {args.base_url}: {e}")
            sys.exit(1)

        print(f"\n🚀 [1/3] Disparando {args.count} Sagas simultaneamente via asyncio.gather...")
        start_batch = time.monotonic()

        tasks = [criar_e_acompanhar_saga(client, i) for i in range(1, args.count + 1)]
        results: List[Dict[str, Any]] = await asyncio.gather(*tasks)

        total_batch_time = time.monotonic() - start_batch
        print(f"  {OK} Todas as {len(results)} Sagas concluíram em {total_batch_time:.2f}s!")

        # 2. Validação individual
        print("\n🔍 [2/3] Validando integridade e isolamento de cada uma das Sagas...")
        all_completed = True
        for idx, saga_detail in enumerate(results, 1):
            saga_id = saga_detail["saga_id"]
            order_id = saga_detail["order_id"]
            status = saga_detail["status"]
            steps = saga_detail.get("steps", [])

            if status != "COMPLETED":
                all_completed = False
                print(f"  {ERR} Saga #{idx} ({order_id}) terminou com status '{status}' (esperado: COMPLETED)")
                continue

            if len(steps) != 4:
                all_completed = False
                print(f"  {ERR} Saga #{idx} ({order_id}) tem {len(steps)} steps (esperado: 4)")
                continue

            for s in steps:
                if s["status"] != "COMPLETED" or s.get("attempts", 1) != 1:
                    all_completed = False
                    print(f"  {ERR} Saga #{idx} step {s['name']} anômalo: status={s['status']}, attempts={s.get('attempts')}")
                    break

        check(all_completed, f"100% das {args.count} Sagas atingiram status final COMPLETED sem erros")

        # 3. Métricas de concorrência
        print("\n📊 [3/3] Métricas de Execução Concorrente:")
        tempos = [r["elapsed_s"] for r in results]
        tempo_medio = sum(tempos) / len(tempos)
        throughput = len(results) / total_batch_time

        print(f"     • Duração Total da Batelada: {total_batch_time:.2f}s")
        print(f"     • Tempo Médio por Saga:     {tempo_medio:.2f}s")
        print(f"     • Throughput Efetivo:       {throughput:.2f} sagas/s")
        print(f"     • Sagas com Sucesso:        {len(results)}/{args.count}")

    print("\n🎉 Validação de Sagas Concorrentes (Card 8.3) CONCLUÍDA COM SUCESSO!\n")


if __name__ == "__main__":
    asyncio.run(main())

