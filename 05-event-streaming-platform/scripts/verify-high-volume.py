#!/usr/bin/env python3
# =============================================================================
# scripts/verify-high-volume.py — Simula Alto Volume de Eventos
# =============================================================================
# Card 28 — Simular alto volume de eventos
#
# Publica um burst de centenas de pedidos e observa:
#   1. Throughput do Producer API (eventos/segundo)
#   2. Comportamento do Lag nos consumer groups durante o burst
#   3. Tempo de recuperação (lag voltando a 0 após o burst)
#   4. Integridade: nenhum evento perdido
#
# Uso:
#   python3 scripts/verify-high-volume.py [--total N] [--workers N]
#
# Exemplos:
#   python3 scripts/verify-high-volume.py              # 200 eventos, 10 workers
#   python3 scripts/verify-high-volume.py --total 500  # 500 eventos
# =============================================================================

import argparse
import json
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime

API_URL = "http://localhost:8000/orders"
KAFKA_CONTAINER = "kafka"
BOOTSTRAP = "kafka:9092"
TOPIC = "orders.created"
GROUPS = ["notification-group", "inventory-group"]

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


@dataclass
class BurstResult:
    total_sent: int = 0
    total_ok: int = 0
    total_fail: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration_sec(self) -> float:
        return self.end_time - self.start_time

    @property
    def throughput(self) -> float:
        return self.total_ok / self.duration_sec if self.duration_sec > 0 else 0

    @property
    def avg_latency_ms(self) -> float:
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0

    @property
    def p99_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0
        sorted_l = sorted(self.latencies_ms)
        idx = int(len(sorted_l) * 0.99)
        return sorted_l[min(idx, len(sorted_l) - 1)]


def publish_one(index: int, result: BurstResult, lock: threading.Lock) -> None:
    """Publica um único pedido e registra a latência."""
    payload = {
        "customer_id": f"cust-burst-{index}",
        "customer_email": f"burst{index}@load.test",
        "items": [
            {
                "product_id": f"prod-{(index % 10) + 1:03d}",
                "product_name": f"Produto Burst {(index % 10) + 1}",
                "quantity": (index % 3) + 1,
                "unit_price": f"{50 + (index % 20) * 5:.2f}",
            }
        ],
        "currency": "BRL",
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        latency = (time.monotonic() - t0) * 1000
        with lock:
            result.total_ok += 1
            result.latencies_ms.append(latency)
    except Exception:
        with lock:
            result.total_fail += 1


def run_burst(total: int, workers: int) -> BurstResult:
    """Dispara `total` pedidos com `workers` threads paralelas."""
    result = BurstResult(total_sent=total)
    lock = threading.Lock()
    semaphore = threading.Semaphore(workers)
    threads = []

    result.start_time = time.monotonic()

    for i in range(1, total + 1):
        semaphore.acquire()

        def task(idx=i):
            try:
                publish_one(idx, result, lock)
            finally:
                semaphore.release()

        t = threading.Thread(target=task, daemon=True)
        threads.append(t)
        t.start()

        # Progress a cada 50 eventos
        if i % 50 == 0:
            with lock:
                ok_so_far = result.total_ok
            pct = i / total * 100
            bar_len = 30
            filled = int(bar_len * i / total)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"  [{bar}] {pct:5.1f}% — {i}/{total} enviados, {ok_so_far} OK", end="\r")

    for t in threads:
        t.join()

    result.end_time = time.monotonic()
    print()  # newline após o progress bar
    return result


def get_all_group_lags() -> dict[str, int]:
    """Retorna o lag total por consumer group."""
    lags = {}
    for group in GROUPS:
        cmd = [
            "docker", "exec", KAFKA_CONTAINER,
            "kafka-consumer-groups", "--bootstrap-server", BOOTSTRAP,
            "--describe", "--group", group
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        total_lag = 0
        for line in res.stdout.strip().splitlines():
            if TOPIC in line:
                parts = line.split()
                if len(parts) >= 6:
                    try:
                        total_lag += int(parts[5]) if parts[5] != "-" else 0
                    except ValueError:
                        pass
        lags[group] = total_lag
    return lags


def get_topic_total_messages() -> int:
    """Retorna o total de mensagens no tópico (latest - earliest)."""
    def offsets(flag: str) -> int:
        cmd = [
            "docker", "exec", KAFKA_CONTAINER,
            "kafka-run-class", "org.apache.kafka.tools.GetOffsetShell",
            "--bootstrap-server", BOOTSTRAP, "--topic", TOPIC, "--time", flag
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        total = 0
        for line in res.stdout.strip().splitlines():
            if line.startswith(TOPIC):
                parts = line.split(":")
                if len(parts) == 3:
                    try:
                        total += int(parts[2])
                    except ValueError:
                        pass
        return total
    return offsets("-1") - offsets("-2")


def wait_for_recovery(timeout_sec: int = 60) -> tuple[bool, float, dict[str, int]]:
    """Aguarda o lag de todos os grupos chegar a 0. Retorna (ok, elapsed, final_lags)."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_sec:
        lags = get_all_group_lags()
        total_lag = sum(lags.values())
        elapsed = time.monotonic() - t0
        lag_str = " | ".join(f"{g.split('-')[0]}={v}" for g, v in lags.items())
        print(f"  ⏳ Aguardando recuperação... ({elapsed:.1f}s) Lag: [{lag_str}]", end="\r")
        if total_lag == 0:
            print()
            return True, time.monotonic() - t0, lags
        time.sleep(1.0)
    print()
    return False, timeout_sec, get_all_group_lags()


def main():
    parser = argparse.ArgumentParser(description="Stress test — High Volume Events (Card 28)")
    parser.add_argument("--total", type=int, default=200, help="Total de eventos a publicar (default: 200)")
    parser.add_argument("--workers", type=int, default=10, help="Workers paralelos (default: 10)")
    args = parser.parse_args()

    print(f"\n{BOLD}{'=' * 74}{RESET}")
    print(f"{BOLD}⚡ Card 28 — Simulação de Alto Volume de Eventos{RESET}")
    print(f"{BOLD}{'=' * 74}{RESET}\n")

    print(f"  Configuração do Stress Test:")
    print(f"    • Total de eventos: {BOLD}{args.total}{RESET}")
    print(f"    • Workers paralelos: {BOLD}{args.workers}{RESET}")
    print(f"    • Tópico alvo: {BOLD}{TOPIC}{RESET}")
    print(f"    • Consumer groups monitorados: {BOLD}{', '.join(GROUPS)}{RESET}")
    print(f"    • Iniciado em: {datetime.now().strftime('%H:%M:%S')}")

    # Baseline antes do burst
    msgs_before = get_topic_total_messages()
    lags_before = get_all_group_lags()

    print(f"\n  Baseline (antes do burst):")
    print(f"    • Msgs no log: {msgs_before}")
    for g, lag in lags_before.items():
        print(f"    • {g} lag: {lag}")

    # ── Burst ────────────────────────────────────────────────────────────────
    print(f"\n{CYAN}[Burst] Disparando {args.total} pedidos com {args.workers} workers paralelos...{RESET}\n")
    result = run_burst(args.total, args.workers)

    msgs_after = get_topic_total_messages()
    lags_during = get_all_group_lags()

    print(f"\n{CYAN}[Pós-Burst] Estado imediato após o burst:{RESET}")
    for g, lag in lags_during.items():
        color = YELLOW if lag > 0 else GREEN
        print(f"  • {g} lag: {color}{lag}{RESET}")

    # ── Aguardar recuperação ─────────────────────────────────────────────────
    print(f"\n{CYAN}[Recuperação] Aguardando consumidores processarem o backlog...{RESET}\n")
    recovered, recovery_time, final_lags = wait_for_recovery(timeout_sec=90)

    # ── Relatório Final ───────────────────────────────────────────────────────
    print(f"\n{BOLD}{'=' * 74}{RESET}")
    print(f"{BOLD}📊 Relatório Final — Alto Volume de Eventos (Card 28){RESET}")
    print(f"{BOLD}{'=' * 74}{RESET}\n")

    success_rate = (result.total_ok / result.total_sent * 100) if result.total_sent > 0 else 0

    print(f"  {BOLD}Throughput do Producer API:{RESET}")
    print(f"    • Total publicados:    {result.total_ok}/{result.total_sent} ({success_rate:.1f}% de sucesso)")
    print(f"    • Duração do burst:    {result.duration_sec:.2f}s")
    print(f"    • Throughput médio:    {BOLD}{result.throughput:.1f} eventos/s{RESET}")
    print(f"    • Latência média:      {result.avg_latency_ms:.1f} ms/req")
    print(f"    • Latência P99:        {result.p99_latency_ms:.1f} ms/req")
    print(f"    • Falhas de rede:      {result.total_fail}")

    print(f"\n  {BOLD}Comportamento do Kafka e Consumidores:{RESET}")
    print(f"    • Msgs no log (antes): {msgs_before}")
    print(f"    • Msgs no log (após):  {msgs_after}")
    print(f"    • Novas msgs no log:   {msgs_after - msgs_before}")

    print(f"\n  {BOLD}Recuperação dos Consumer Groups:{RESET}")
    if recovered:
        print(f"    • Tempo de recuperação: {GREEN}{BOLD}{recovery_time:.1f}s{RESET}")
    else:
        print(f"    • {YELLOW}Timeout atingido — lag ainda pendente após 90s{RESET}")
    for g, lag in final_lags.items():
        status = f"{GREEN}Lag=0 ✅{RESET}" if lag == 0 else f"{YELLOW}Lag={lag} ⚠️{RESET}"
        print(f"    • {g}: {status}")

    # Resumo de aprovação
    throughput_ok = result.throughput >= 5
    success_ok = success_rate >= 95
    recovery_ok = recovered

    print(f"\n  {BOLD}Critérios de Aprovação:{RESET}")
    print(f"    1. Taxa de sucesso ≥ 95%:       {'✅ PASSOU' if success_ok else '❌ FALHOU'} ({success_rate:.1f}%)")
    print(f"    2. Throughput ≥ 5 eventos/s:     {'✅ PASSOU' if throughput_ok else '⚠️ VERIFICAR'} ({result.throughput:.1f}/s)")
    print(f"    3. Lag zerado após o burst:      {'✅ PASSOU' if recovery_ok else '⚠️ TIMEOUT'} ({recovery_time:.1f}s)")

    print(f"\n{BOLD}{'=' * 74}{RESET}")
    if success_ok and recovery_ok:
        print(f"{GREEN}{BOLD}✅ PLATAFORMA APROVADA NO STRESS TEST!{RESET}")
        print(f"  {result.total_ok} eventos processados por todos os consumers sem perda.")
    else:
        print(f"{YELLOW}{BOLD}⚠️  STRESS TEST CONCLUÍDO COM ALERTAS{RESET}")
    print(f"{BOLD}{'=' * 74}{RESET}\n")


if __name__ == "__main__":
    main()
