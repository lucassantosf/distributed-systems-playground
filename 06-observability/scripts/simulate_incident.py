#!/usr/bin/env python3
"""
simulate_incident.py — Simulação de Cenário de Incidente e Degradação
Card 19

Simula degradação por um período de tempo (padrão 2 minutos / 120s):
  - 30% das requisições com latência elevada (2.0s a 3.0s em /debug/slow)
  - 10% das requisições com erro 500 (/debug/error)
  - 60% das requisições normais (GET /orders, POST /orders em sample-app e producer-api)

Permite acompanhar em tempo real:
  - Métrica: elevação do P95/P99 e taxa de erro no Grafana
  - Alertas: disparo de HighLatency no Alertmanager
  - Traces: Spans com duração elevadas no Tempo
  - Logs: registros de ERROR/WARNING com trace_id no OpenSearch
"""
import argparse
import random
import sys
import time
import urllib.request
import urllib.error

SAMPLE_APP_URL = "http://localhost:8000"
PRODUCER_API_URL = "http://localhost:8001"


def send_normal_req():
    r = random.random()
    if r < 0.5:
        url = f"{SAMPLE_APP_URL}/orders"
        req = urllib.request.Request(url, method="GET")
    else:
        url = f"{PRODUCER_API_URL}/orders"
        payload = b'{"customer_id":"incident_test","customer_email":"inc@test.com","items":[{"product_id":"p1","product_name":"Item Teste Incidente","quantity":1,"unit_price":10.0}],"currency":"BRL"}'
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 500


def send_slow_req():
    delay = round(random.uniform(2.0, 3.0), 2)
    url = f"{SAMPLE_APP_URL}/debug/slow?delay={delay}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except Exception:
        return 500


def send_error_req():
    url = f"{SAMPLE_APP_URL}/debug/error"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 500


def main():
    parser = argparse.ArgumentParser(description="Simulador de Incidente para Observabilidade (Card 19)")
    parser.add_argument("--duration", type=int, default=120, help="Duração da simulação em segundos (padrão: 120s)")
    args = parser.parse_args()

    duration_sec = args.duration
    start_time = time.time()
    end_time = start_time + duration_sec

    total_reqs = 0
    slow_count = 0
    error_count = 0
    normal_count = 0

    print("=" * 70)
    print("  SIMULAÇÃO DE INCIDENTE E DEGRADAÇÃO — CARD 19")
    print(f"  Duração: {duration_sec} segundos")
    print("  Cenário:")
    print("    - 30% das requisições com delay artificial (2.0s - 3.0s)")
    print("    - 10% das requisições com Erro 500")
    print("    - 60% requisições normais (sample-app & producer-api)")
    print("  Dashboards para Acompanhamento:")
    print("    - Metrics Overview:  http://localhost:3000/d/sample-app-metrics")
    print("    - Projeto 05:        http://localhost:3000/d/project-05-event-streaming")
    print("    - Logs Overview:     http://localhost:3000/d/sample-app-logs")
    print("    - Alertmanager UI:   http://localhost:9093")
    print("=" * 70)
    print()

    try:
        while time.time() < end_time:
            roll = random.random()
            total_reqs += 1

            if roll < 0.10:  # 10% erro 500
                status = send_error_req()
                error_count += 1
                kind = "ERROR 500 ⚠️"
            elif roll < 0.40:  # 30% lentas (2-3s)
                status = send_slow_req()
                slow_count += 1
                kind = "SLOW (2-3s) 🐢"
            else:  # 60% normais
                status = send_normal_req()
                normal_count += 1
                kind = "NORMAL 200/201 ✅"

            elapsed = int(time.time() - start_time)
            print(f"[{elapsed:03d}s/{duration_sec}s] Reqs: {total_reqs:3d} | {kind:15} (HTTP {status}) | Normais: {normal_count:2d}, Lentas: {slow_count:2d}, Erros: {error_count:2d}")

            time.sleep(0.3)

    except KeyboardInterrupt:
        print("\n\nSimulação interrompida pelo usuário.")

    print("\n")
    print("=" * 70)
    print("  RESUMO DA SIMULAÇÃO DE INCIDENTE")
    print("=" * 70)
    print(f"  Total de Requisições: {total_reqs}")
    print(f"  Normais (2xx):        {normal_count} ({normal_count / max(total_reqs, 1) * 100:.1f}%)")
    print(f"  Lentas (2-3s):        {slow_count} ({slow_count / max(total_reqs, 1) * 100:.1f}%)")
    print(f"  Erros (5xx):          {error_count} ({error_count / max(total_reqs, 1) * 100:.1f}%)")
    print("=" * 70)


if __name__ == "__main__":
    main()
