"""
stress_test.py — Stress Test de Throughput e Latência (Card 8.4)

Roteiro de Teste de Carga e Estresse:
  1. Dispara N Sagas (default: 100) com concorrência controlada via semáforo.
  2. Acompanha cada Saga até atingir status terminal (COMPLETED, COMPENSATED ou FAILED).
  3. Coleta latências de ponta a ponta (end-to-end) em segundos e milissegundos.
  4. Calcula métricas estatísticas:
     - Throughput global (Sagas/s)
     - Percentis de latência: P50 (mediana), P90, P95, P99 e Máxima
     - Taxa de sucesso (Success Rate)
  5. Valida a meta de resiliência: ZERO Sagas travadas ou sem status final.

Uso:
  python3 scripts/stress_test.py
  python3 scripts/stress_test.py --count 100 --concurrency 20 --base-url http://localhost:8090
"""
import argparse
import asyncio
import math
import os
import sys
import time
import uuid
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:
    httpx = None

POLL_INTERVAL_S = 0.5
POLL_TIMEOUT_S = 60

OK = "✅"
ERR = "❌"
WARN = "⚠️"
INFO = "ℹ️ "


def calculate_percentile(sorted_values: List[float], percentile: float) -> float:
    """Calcula percentil usando interpolação linear padrão (P50, P95, P99)."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]

    k = (len(sorted_values) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[int(f)] * (c - k)
    d1 = sorted_values[int(c)] * (k - f)
    return d0 + d1


class StressMetrics:
    def __init__(self, total_sagas: int):
        self.total_sagas = total_sagas
        self.completed_count = 0
        self.compensated_count = 0
        self.failed_count = 0
        self.stuck_count = 0
        self.durations: List[float] = []
        self.total_wall_time_s = 0.0

    @property
    def finished_count(self) -> int:
        return self.completed_count + self.compensated_count + self.failed_count

    @property
    def throughput(self) -> float:
        if self.total_wall_time_s <= 0:
            return 0.0
        return self.finished_count / self.total_wall_time_s

    def compute_percentiles(self) -> Dict[str, float]:
        if not self.durations:
            return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0, "min": 0.0, "avg": 0.0}

        sorted_durations = sorted(self.durations)
        return {
            "p50": calculate_percentile(sorted_durations, 50),
            "p90": calculate_percentile(sorted_durations, 90),
            "p95": calculate_percentile(sorted_durations, 95),
            "p99": calculate_percentile(sorted_durations, 99),
            "max": sorted_durations[-1],
            "min": sorted_durations[0],
            "avg": sum(sorted_durations) / len(sorted_durations),
        }


async def executar_saga_individual(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    index: int,
    timeout_s: float = POLL_TIMEOUT_S,
) -> Dict[str, Any]:
    async with semaphore:
        order_id = f"ORD-STRESS-{index:04d}-{uuid.uuid4().hex[:6]}"
        payload = {
            "order_id": order_id,
            "customer_id": f"cust-stress-{index}",
            "items": [{"sku": f"PROD-STRESS-{index % 10}", "quantity": 1, "unit_price": 50.0}],
            "total_amount": 50.0,
            "shipping_address": f"Rua Stress, {index} - SP",
            "payment_method": "credit_card",
        }

        start_time = time.monotonic()
        try:
            res = await client.post("/sagas", json=payload)
            if res.status_code != 202:
                return {
                    "index": index,
                    "order_id": order_id,
                    "status": "HTTP_ERROR",
                    "error": f"POST retornou {res.status_code}: {res.text[:100]}",
                    "elapsed_s": time.monotonic() - start_time,
                }

            saga_id = res.json()["saga_id"]
        except Exception as exc:
            return {
                "index": index,
                "order_id": order_id,
                "status": "NETWORK_ERROR",
                "error": str(exc),
                "elapsed_s": time.monotonic() - start_time,
            }

        # Polling até atingir status terminal
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                d_res = await client.get(f"/sagas/{saga_id}")
                if d_res.status_code == 200:
                    detail = d_res.json()
                    st = detail.get("status")
                    if st in ("COMPLETED", "COMPENSATED", "FAILED"):
                        return {
                            "index": index,
                            "saga_id": saga_id,
                            "order_id": order_id,
                            "status": st,
                            "elapsed_s": time.monotonic() - start_time,
                            "steps_count": len(detail.get("steps", [])),
                        }
            except Exception:
                pass
            await asyncio.sleep(POLL_INTERVAL_S)

        return {
            "index": index,
            "saga_id": saga_id,
            "order_id": order_id,
            "status": "STUCK",
            "error": f"Timeout após {timeout_s}s sem atingir status terminal",
            "elapsed_s": time.monotonic() - start_time,
        }


async def main():
    if httpx is None:
        print("❌ Dependência ausente: instale com 'pip install httpx'")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Stress Test de Throughput e Latência (Card 8.4)")
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Quantidade total de Sagas a disparar (default: 100)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=25,
        help="Nível máximo de concorrência simultânea (default: 25)",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("ORCHESTRATOR_URL", "http://localhost:8090"),
        help="URL base do Saga Orchestrator",
    )
    args = parser.parse_args()

    print("\n" + "=" * 75)
    print("  🔥 SAGA ORCHESTRATOR — STRESS TEST DE THROUGHPUT E LATÊNCIA (CARD 8.4)")
    print("=" * 75)
    print(f"  Target:            {args.base_url}")
    print(f"  Total de Sagas:    {args.count}")
    print(f"  Concorrência Máx:  {args.concurrency}")
    print(f"  Timeout por Saga:  {POLL_TIMEOUT_S}s\n")

    limits = httpx.Limits(max_keepalive_connections=args.concurrency, max_connections=args.concurrency * 2)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=25.0, limits=limits) as client:
        # 1. Healthcheck
        try:
            h = await client.get("/health")
            if h.status_code != 200:
                print(f"❌ Orquestrador não saudável em {args.base_url}/health (status={h.status_code})")
                sys.exit(1)
        except Exception as e:
            print(f"❌ Conexão recusada ao orquestrador em {args.base_url}: {e}")
            sys.exit(1)

        print(f"🚀 Iniciando disparo de {args.count} Sagas...")
        semaphore = asyncio.Semaphore(args.concurrency)
        metrics = StressMetrics(total_sagas=args.count)

        wall_start = time.monotonic()
        tasks = [executar_saga_individual(client, semaphore, i) for i in range(1, args.count + 1)]
        results: List[Dict[str, Any]] = await asyncio.gather(*tasks)
        metrics.total_wall_time_s = time.monotonic() - wall_start

        # Consolidação de métricas
        for r in results:
            st = r.get("status")
            elapsed = r.get("elapsed_s", 0.0)
            if st == "COMPLETED":
                metrics.completed_count += 1
                metrics.durations.append(elapsed)
            elif st == "COMPENSATED":
                metrics.compensated_count += 1
                metrics.durations.append(elapsed)
            elif st == "FAILED":
                metrics.failed_count += 1
                metrics.durations.append(elapsed)
            else:
                metrics.stuck_count += 1

        percentiles = metrics.compute_percentiles()

        # Relatório Final
        print("\n" + "=" * 75)
        print("  📊 RESULTADO FINAL DO STRESS TEST")
        print("=" * 75)
        print(f"  • Tempo Total de Execução:    {metrics.total_wall_time_s:.2f}s")
        print(f"  • Sagas Disparadas:           {metrics.total_sagas}")
        print(f"  • Sagas Concluídas (COMPLETED): {metrics.completed_count} ({metrics.completed_count / metrics.total_sagas * 100:.1f}%)")
        print(f"  • Sagas Compensadas:          {metrics.compensated_count}")
        print(f"  • Sagas com Falha Terminal:   {metrics.failed_count}")
        print(f"  • Sagas Travadas (STUCK):     {metrics.stuck_count}")
        print("-" * 75)
        print(f"  • ⚡ Throughput Médio:         {metrics.throughput:.2f} Sagas/s")
        print(f"  • ⏱️  Latência Mínima:         {percentiles['min']:.3f}s ({percentiles['min'] * 1000:.0f}ms)")
        print(f"  • ⏱️  Latência Média:          {percentiles['avg']:.3f}s ({percentiles['avg'] * 1000:.0f}ms)")
        print(f"  • ⏱️  Latência P50 (Mediana):  {percentiles['p50']:.3f}s ({percentiles['p50'] * 1000:.0f}ms)")
        print(f"  • ⏱️  Latência P90:            {percentiles['p90']:.3f}s ({percentiles['p90'] * 1000:.0f}ms)")
        print(f"  • ⏱️  Latência P95:            {percentiles['p95']:.3f}s ({percentiles['p95'] * 1000:.0f}ms)")
        print(f"  • ⏱️  Latência P99:            {percentiles['p99']:.3f}s ({percentiles['p99'] * 1000:.0f}ms)")
        print(f"  • ⏱️  Latência Máxima:         {percentiles['max']:.3f}s ({percentiles['max'] * 1000:.0f}ms)")
        print("=" * 75)

        # Critério de Aceitação do Card 8.4: 0 Sagas travadas
        if metrics.stuck_count == 0 and metrics.finished_count == metrics.total_sagas:
            print(f"  🎉 SUCESSO: 0 Sagas travadas! Meta do Card 8.4 atingida! {OK}")
            print("=" * 75 + "\n")
            sys.exit(0)
        else:
            print(f"  ❌ FALHA: {metrics.stuck_count} Sagas ficaram travadas sem status final! {ERR}")
            print("=" * 75 + "\n")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

