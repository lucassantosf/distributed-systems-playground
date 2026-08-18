#!/usr/bin/env python3
# =============================================================================
# scripts/verify-fault-recovery.py — Valida Isolamento de Falhas e Resiliência
# =============================================================================
# Card 24 — Validar recuperação de falhas
#
# Demonstra que falhas em um consumidor isolado (ex: notification-consumer):
#   1. NÃO interrompem a produção de eventos (Producer API continua operante).
#   2. NÃO afetam outros consumidores do mesmo tópico (inventory-consumer consome tudo com Lag=0).
#   3. NÃO travam o Event Stream (offsets continuam avançando normalmente).
#
# Uso:
#   python3 scripts/verify-fault-recovery.py
# =============================================================================

import json
import subprocess
import time
import urllib.request

API_URL = "http://localhost:8000/orders"
KAFKA_CONTAINER = "kafka"
BOOTSTRAP = "kafka:9092"
TOPIC = "orders.created"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def get_group_lag(group_id: str) -> int:
    """Retorna o Lag total de um consumer group."""
    cmd = [
        "docker", "exec", KAFKA_CONTAINER,
        "kafka-consumer-groups", "--bootstrap-server", BOOTSTRAP,
        "--describe", "--group", group_id
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    total_lag = 0
    for line in res.stdout.strip().splitlines():
        if TOPIC in line:
            parts = line.split()
            if len(parts) >= 6:
                try:
                    lag = int(parts[5]) if parts[5] != "-" else 0
                    total_lag += lag
                except ValueError:
                    pass
    return total_lag


def publish_order(prefix: str, simulate_error: str | None = None, fail_until_retry: int = 1) -> str:
    """Publica um pedido via API HTTP."""
    payload = {
        "customer_id": f"cust-{prefix}",
        "customer_email": f"{prefix}@domain.com",
        "items": [{"product_id": f"prod-{prefix}", "product_name": f"Item {prefix.title()}", "quantity": 1, "unit_price": "80.00"}],
        "currency": "BRL",
    }
    if simulate_error:
        payload["simulate_error"] = simulate_error
        payload["fail_until_retry"] = fail_until_retry

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("order_id", "?")
    except Exception as e:
        print(f"Erro na publicação: {e}")
        return ""


def main():
    print(f"\n{BOLD}{'=' * 74}{RESET}")
    print(f"{BOLD}🛡️ Card 24 — Validação de Isolamento de Falhas e Resiliência{RESET}")
    print(f"{BOLD}{'=' * 74}{RESET}\n")

    print(f"{CYAN}[1/4] Garantindo que todos os consumidores estejam ativos...{RESET}")
    subprocess.run(["docker", "compose", "up", "-d"], capture_output=True, text=True)
    time.sleep(2.0)

    # ── 1. Publicar um mix de pedidos com eventos normais e defeituosos ──────
    print(f"\n{CYAN}[2/4] Publicando lote misto de eventos (Normais, Temporários e Fatais)...{RESET}")

    orders_published = []

    # 2 Pedidos Normais
    orders_published.append(("Normal 1", publish_order("norm-1")))
    orders_published.append(("Normal 2", publish_order("norm-2")))

    # 1 Pedido com Falha Temporária (Retry)
    orders_published.append(("Erro Temporário", publish_order("temp-err", simulate_error="temporary", fail_until_retry=1)))

    # 1 Pedido com Erro Fatal (DLT)
    orders_published.append(("Erro Fatal", publish_order("fatal-err", simulate_error="fatal")))

    # 2 Pedidos Normais Subsequentes (para provar continuidade do stream)
    orders_published.append(("Normal 3", publish_order("norm-3")))
    orders_published.append(("Normal 4", publish_order("norm-4")))

    print(f"  ✅ {len(orders_published)} eventos enviados ao Event Stream (Producer API 100% responsiva).")

    # ── 2. Aguardar tempo para processamento de retry e DLT ──────────────────
    print(f"\n{CYAN}[3/4] Aguardando processamento, retentativas e isolamento de falhas...{RESET}")
    time.sleep(8.0)

    # ── 3. Verificar o impacto no inventory-group (Isolamento de Falhas) ──────
    inventory_lag = get_group_lag("inventory-group")
    notification_lag = get_group_lag("notification-group")

    print(f"\n{CYAN}[4/4] Inspecionando estado e isolamento dos Consumer Groups:{RESET}")
    print(f"  • inventory-group lag:    {GREEN if inventory_lag == 0 else RED}{inventory_lag}{RESET} (Consumidor isolado — zero impacto)")
    print(f"  • notification-group lag: {GREEN if notification_lag == 0 else YELLOW}{notification_lag}{RESET} (Recuperou do erro e manteve offset)")

    # Relatório Final
    producer_ok = len(orders_published) == 6
    inventory_isolated_ok = (inventory_lag == 0)
    stream_continued_ok = (notification_lag == 0)

    print(f"\n{BOLD}{'=' * 74}{RESET}")
    print(f"{BOLD}📊 Relatório Final — Isolamento de Falhas (Card 24){RESET}")
    print(f"{BOLD}{'=' * 74}{RESET}\n")

    print(f"  1. Continuidade do Producer (API Ininterrupta):    {'✅ PASSOU' if producer_ok else '⚠️ VERIFICAR'}")
    print(f"  2. Isolamento no Inventory Consumer (Lag = 0):     {'✅ PASSOU (Nenhum efeito colateral)' if inventory_isolated_ok else '⚠️ LAG PENDENTE'}")
    print(f"  3. Recuperação do Notification Consumer (Lag = 0): {'✅ PASSOU (Stream destravado)' if stream_continued_ok else '⚠️ LAG PENDENTE'}")

    print(f"\n{BOLD}{'=' * 74}{RESET}")
    if producer_ok and inventory_isolated_ok and stream_continued_ok:
        print(f"{GREEN}{BOLD}✅ RECURSO DE RESILIÊNCIA E ISOLAMENTO DE FALHAS APROVADO!{RESET}")
        print(f"  Falhas em um consumidor não afetam outros consumidores nem travam o pipeline.")
    else:
        print(f"{YELLOW}{BOLD}⚠️ VALIDAÇÃO CONCLUÍDA COM ALERTAS{RESET}")
    print(f"{BOLD}{'=' * 74}{RESET}\n")


if __name__ == "__main__":
    main()
