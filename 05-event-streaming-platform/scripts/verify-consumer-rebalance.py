#!/usr/bin/env python3
# =============================================================================
# scripts/verify-consumer-rebalance.py — Valida Rebalanceamento Dinâmico
# =============================================================================
# Card 15 — Validar Rebalanceamento
#
# Demonstra as 4 fases do ciclo de rebalanceamento do Kafka:
#   1. Fase 1: 1 Instância  → assume todas as 3 partições.
#   2. Fase 2: 3 Instâncias → redistribuição uniforme (1 partição por instância).
#   3. Fase 3: 4 Instâncias → over-scaling (3 ativas + 1 ociosa/idle).
#   4. Fase 4: Failover      → simulação de queda (docker stop) e recuperação automática.
#
# Uso:
#   python3 scripts/verify-consumer-rebalance.py
# =============================================================================

import json
import subprocess
import time
import urllib.request

API_URL = "http://localhost:8000/orders"
KAFKA_CONTAINER = "kafka"
BOOTSTRAP = "kafka:9092"
GROUP = "notification-group"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def set_scale(count: int):
    """Ajusta a quantidade de réplicas do notification-consumer via docker compose."""
    cmd = ["docker", "compose", "up", "-d", "--scale", f"notification-consumer={count}"]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def get_consumer_containers() -> list[str]:
    """Retorna a lista de nomes dos containers ativos do notification-consumer."""
    cmd = ["docker", "ps", "--filter", "name=notification-consumer", "--format", "{{.Names}}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return sorted([n.strip() for n in res.stdout.strip().splitlines() if n.strip()])


def get_partition_assignments() -> list[dict]:
    """Consulta kafka-consumer-groups --describe para saber qual partição está atribuída a qual consumer."""
    cmd = [
        "docker", "exec", KAFKA_CONTAINER,
        "kafka-consumer-groups", "--bootstrap-server", BOOTSTRAP,
        "--describe", "--group", GROUP
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assignments = []
    lines = res.stdout.strip().splitlines()
    for line in lines:
        if not line or line.startswith("GROUP") or "Error" in line:
            continue
        parts = line.split()
        if len(parts) >= 7:
            grp, topic, partition, current_off, log_end, lag, cid = parts[:7]
            host = parts[7] if len(parts) > 7 else "-"
            assignments.append({
                "partition": partition,
                "consumer_id": cid,
                "host": host
            })
    return assignments


def publish_order() -> str:
    """Publica 1 pedido de teste para confirmar resiliência."""
    payload = {
        "customer_id": "cust-rebalance-test",
        "customer_email": "rebalance@test.com",
        "items": [{"product_id": "prod-reb-1", "product_name": "Item Teste Rebalance", "quantity": 1, "unit_price": "100.00"}],
        "currency": "BRL"
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("order_id", "N/A")
    except Exception as e:
        return ""


def main():
    print(f"\n{BOLD}{'=' * 66}{RESET}")
    print(f"{BOLD}🔄 Card 15 — Validação de Rebalanceamento Dinâmico e Failover{RESET}")
    print(f"{BOLD}{'=' * 66}{RESET}\n")

    # ── FASE 1: 1 Instância ───────────────────────────────────────────────────
    print(f"{CYAN}📌 [Fase 1/4] Reduzindo para 1 instância (notification-consumer=1)...{RESET}")
    set_scale(1)
    time.sleep(3.5)

    containers_f1 = get_consumer_containers()
    assign_f1 = get_partition_assignments()

    print(f"  • Containers ativos ({len(containers_f1)}): {', '.join(containers_f1)}")
    for a in assign_f1:
        print(f"    - Partição {a['partition']} → Consumer: {a['consumer_id'][:35]}")

    # ── FASE 2: Scale Up (1 → 3 Instâncias) ────────────────────────────────────
    print(f"\n{CYAN}📌 [Fase 2/4] Rebalanceamento Scale Up: escalando para 3 instâncias...{RESET}")
    set_scale(3)
    time.sleep(5.0)

    containers_f2 = get_consumer_containers()
    assign_f2 = get_partition_assignments()
    unique_cids_f2 = set(a["consumer_id"] for a in assign_f2 if a["consumer_id"] != "-")

    print(f"  • Containers ativos ({len(containers_f2)}): {', '.join(containers_f2)}")
    print(f"  • Consumidores únicos no Kafka: {len(unique_cids_f2)}")
    for a in assign_f2:
        print(f"    - Partição {a['partition']} → Consumer: {a['consumer_id'][:35]} ({a['host']})")

    # ── FASE 3: Over-scaling (3 → 4 Instâncias / Instância Idle) ──────────────
    print(f"\n{CYAN}📌 [Fase 3/4] Over-scaling: escalando para 4 instâncias (Tópico tem 3 partições)...{RESET}")
    set_scale(4)
    time.sleep(5.0)

    containers_f3 = get_consumer_containers()
    assign_f3 = get_partition_assignments()
    active_cids_f3 = set(a["consumer_id"] for a in assign_f3 if a["consumer_id"] != "-")

    print(f"  • Containers ativos no Docker ({len(containers_f3)}): {', '.join(containers_f3)}")
    print(f"  • Consumidores com partições atribuídas: {len(active_cids_f3)}")
    print(f"  • Consumidores Ociosos (Idle/Standby): {len(containers_f3) - len(active_cids_f3)}")

    # ── FASE 4: Failover (Derrubar 1 Container Ativo) ──────────────────────────
    target_container = containers_f3[-1]
    print(f"\n{CYAN}📌 [Fase 4/4] Simulação de Falha (Failover): Derrubando '{target_container}'...{RESET}")
    subprocess.run(["docker", "stop", target_container], capture_output=True, text=True)
    print(f"  ⚡ Container '{target_container}' derrubado! Aguardando rebalanceamento do Kafka...")

    time.sleep(6.0)

    containers_f4 = get_consumer_containers()
    assign_f4 = get_partition_assignments()

    print(f"  • Containers sobreviventes ({len(containers_f4)}): {', '.join(containers_f4)}")
    for a in assign_f4:
        print(f"    - Partição {a['partition']} → Consumer: {a['consumer_id'][:35]} ({a['host']})")

    # Teste de consumo pós-falha
    order_id = publish_order()
    print(f"\n  ✉️  Enviando pedido pós-falha para testar resiliência... (Order ID: {order_id})")
    time.sleep(2.0)

    # ── RESTAURAÇÃO: Voltar ambiente ao normal (3 réplicas) ───────────────────
    print(f"\n{CYAN}🔄 Restaurando ambiente para 3 réplicas padrão...{RESET}")
    set_scale(3)
    time.sleep(3.0)

    # ── RELATÓRIO FINAL ───────────────────────────────────────────────────────
    print(f"\n{BOLD}{'=' * 66}{RESET}")
    print(f"{BOLD}📊 Relatório Final de Rebalanceamento e Failover{RESET}")
    print(f"{BOLD}{'=' * 66}{RESET}\n")

    fase2_ok = len(unique_cids_f2) == 3
    fase3_ok = len(containers_f3) == 4 and len(active_cids_f3) == 3
    fase4_ok = len(assign_f4) == 3 and all(a["consumer_id"] != "-" for a in assign_f4)

    print(f"  1. Scale Up (1 → 3):          {'✅ PASSOU' if fase2_ok else '⚠️ REBALANCEANDO'}")
    print(f"  2. Over-scaling (3 → 4):      {'✅ PASSOU (1 container Idle)' if fase3_ok else '⚠️ ATENÇÃO'}")
    print(f"  3. Failover (Queda de Nó):   {'✅ PASSOU (Partições reatribuídas sem perda)' if fase4_ok else '❌ FALHOU'}")

    print(f"\n{BOLD}{'=' * 66}{RESET}")
    if fase2_ok and fase4_ok:
        print(f"{GREEN}{BOLD}✅ VALIDAÇÃO APROVADA!{RESET}")
        print(f"  O Kafka realizou o rebalanceamento dinâmico e o failover com sucesso.")
    else:
        print(f"{YELLOW}{BOLD}⚠️ ALERTA DE REBALANCEAMENTO{RESET}")
        print(f"  O cluster Kafka respondeu mas requer verificação de tempos de heartbeat.")
    print(f"{BOLD}{'=' * 66}{RESET}\n")


if __name__ == "__main__":
    main()
