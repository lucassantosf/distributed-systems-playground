#!/usr/bin/env python3
"""
simulate_incident.py — Simulação de Cenário de Incidente e Degradação
Card 19

Simula degradação por um período de tempo (padrão 2 minutos):
  - 30% das requisições com latência elevada (endpoint /debug/slow ou delay)
  - 10% das requisições com erro 500 (endpoint /debug/error)
  - 60% requisições normais (GET /orders, POST /orders)

Exibe em tempo real o progresso e estatísticas.
"""
import argparse
import random
import sys
import time
import urllib.request

APP_URL = "http://localhost:8000"


def send_normal_req():
    r = random.random()
    if r < 0.5:
        url = f"{APP_URL}/orders"
        req = urllib.request.Request(url, method="GET")
    else:
        url = f"{APP_URL}/orders"
        payload = b'{"item": "Incident Test Item"}'
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 500


def send_slow_req():
    url = f"{APP_URL}/debug/slow"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status
    except Exception:
        return 500


def send_error_req():
    url = f"{APP_URL}/debug/error"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 500


def main():
    parser = argparse.ArgumentParser(description="Simulador de Incidente para Observabilidade")
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
    print("  Acompanhe no Grafana:")
    print("    - Dashboard Métricas: http://localhost:3000/d/sample-app-metrics")
    print("    - Dashboard Logs:     http://localhost:3000/d/sample-app-logs")
    print("    - Dashboard Traces:   http://localhost:3000/d/sample-app-traces")
    print("    - Alertmanager UI:    http://localhost:9093")
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
            elif roll < 0.40:  # 30% lentas (600ms+)
                status = send_slow_req()
                slow_count += 1
                kind = "SLOW (600ms) 🐢"
            else:  # 60% normais
                status = send_normal_req()
                normal_count += 1
                kind = "NORMAL 200/201 ✅"

            elapsed = int(time.time() - start_time)
            remaining = duration_sec - elapsed
            print(f"[{elapsed:03d}s/{duration_sec}s] Reqs: {total_reqs} | {kind} (HTTP {status}) | Normais: {normal_count}, Lentas: {slow_count}, Erros: {error_count}", end="\r")

            time.sleep(0.4)

    except KeyboardInterrupt:
        print("\n\nSimulação interrompida pelo usuário.")

    print("\n")
    print("=" * 70)
    print("  RESUMO DA SIMULAÇÃO DE INCIDENTE")
    print("=" * 70)
    print(f"  Total de Requisições: {total_reqs}")
    print(f"  Normais (2xx):        {normal_count} ({normal_count / max(total_reqs, 1) * 100:.1f}%)")
    print(f"  Lentas (600ms+):      {slow_count} ({slow_count / max(total_reqs, 1) * 100:.1f}%)")
    print(f"  Erros (5xx):          {error_count} ({error_count / max(total_reqs, 1) * 100:.1f}%)")
    print("=" * 70)


if __name__ == "__main__":
    main()
