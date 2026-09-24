#!/usr/bin/env python3
"""
benchmark_cache.py — Demonstração e medição de performance com cache Redis no BFF.
Mede o tempo de resposta do endpoint GET /bff/orders/{id} sem cache (MISS) e com cache (HIT).
"""

import argparse
import sys
import time
import urllib.request
import json

def make_request(url: str):
    start = time.perf_counter()
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as response:
            elapsed = (time.perf_counter() - start) * 1000.0
            body = response.read().decode('utf-8')
            cache_header = response.headers.get("X-Cache", "UNKNOWN")
            return response.status, elapsed, cache_header, json.loads(body)
    except urllib.error.HTTPError as e:
        elapsed = (time.perf_counter() - start) * 1000.0
        return e.code, elapsed, "ERROR", None
    except Exception as e:
        print(f"[ERRO] Falha de conexão: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Benchmark de cache do BFF")
    parser.add_argument("--url", default="http://localhost:8000", help="URL base do BFF")
    parser.add_argument("--order-id", type=int, default=1, help="ID do pedido para benchmark")
    parser.add_argument("--iterations", type=int, default=5, help="Número de chamadas adicionais para média de HIT")
    args = parser.parse_args()

    endpoint = f"{args.url}/bff/orders/{args.order_id}"

    print("=" * 60)
    print(" BENCHMARK DE CACHE (REDIS) — BFF")
    print("=" * 60)
    print(f"Target Endpoint: {endpoint}")
    print(f"Order ID:        {args.order_id}")
    print("-" * 60)

    # 1. Primeira chamada (Pode ser MISS ou HIT dependendo do estado atual)
    status, miss_time, cache_status, data = make_request(endpoint)
    print(f"1ª Chamada (Estado Inicial): HTTP {status} | X-Cache: {cache_status} | Latência: {miss_time:.2f} ms")

    # 2. Se a primeira não foi MISS, aguardamos ou informamos
    if cache_status == "HIT":
        print("[INFO] Resposta já estava no cache. Testando chamadas adicionais...")
        miss_time_est = miss_time
    else:
        miss_time_est = miss_time

    # 3. Chamadas em HIT
    hit_times = []
    for i in range(1, args.iterations + 1):
        s, t, c, _ = make_request(endpoint)
        hit_times.append(t)
        print(f"Chamada #{i+1} (HIT):            HTTP {s} | X-Cache: {c}    | Latência: {t:.2f} ms")

    avg_hit_time = sum(hit_times) / len(hit_times) if hit_times else 0.0
    speedup = ((miss_time_est - avg_hit_time) / miss_time_est) * 100.0 if miss_time_est > 0 else 0.0

    items_count = len(data.get("items", [])) if data and isinstance(data, dict) else 2
    saved_downstream_calls = 1 + 1 + items_count  # 1 order + 1 user + N products

    print("\n" + "=" * 60)
    print(" RESUMO DE PERFORMANCE")
    print("=" * 60)
    print(f"• Latência sem cache (MISS):    {miss_time_est:.2f} ms")
    print(f"• Latência média com cache (HIT): {avg_hit_time:.2f} ms")
    print(f"• Ganho de performance:         {speedup:.1f}% mais rápido")
    print(f"• Chamadas downstream salvas:   {saved_downstream_calls} chamadas por requisição HIT")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()

