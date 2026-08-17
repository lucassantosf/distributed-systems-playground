#!/usr/bin/env python3
# =============================================================================
# scripts/verify-offsets-behavior.py — Inspeção e Auditoria de Offsets Kafka
# =============================================================================
# Card 16 — Explorar Funcionamento dos Offsets
#
# O que este script faz:
#   1. Mapeia os offsets de cada partição do tópico 'orders.created':
#      - Earliest Offset (primeiro offset disponível no log)
#      - Log-End-Offset (LEO — próximo offset a ser gravado pelo producer)
#   2. Mapeia a posição de leitura (Committed Offset) e Lag para cada Consumer Group:
#      - notification-group
#      - inventory-group
#   3. Envia 5 novos pedidos via API e demonstra o avanço em tempo real dos offsets.
#
# Uso:
#   python3 scripts/verify-offsets-behavior.py
# =============================================================================

import json
import subprocess
import time
import urllib.request

API_URL = "http://localhost:8000/orders"
KAFKA_CONTAINER = "kafka"
BOOTSTRAP = "kafka:9092"
TOPIC = "orders.created"
GROUPS = ["notification-group", "inventory-group"]

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def get_log_offsets(time_flag: str = "-1") -> dict[int, int]:
    """
    Retorna o offset do tópico por partição.
      time_flag="-1" -> Latest Offset / Log-End-Offset (LEO)
      time_flag="-2" -> Earliest Offset (Menor offset disponível)
    """
    cmd = [
        "docker", "exec", KAFKA_CONTAINER,
        "kafka-run-class", "org.apache.kafka.tools.GetOffsetShell",
        "--bootstrap-server", BOOTSTRAP,
        "--topic", TOPIC,
        "--time", time_flag
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    offsets = {}
    for line in res.stdout.strip().splitlines():
        if line.startswith(TOPIC):
            parts = line.split(":")
            if len(parts) == 3:
                partition = int(parts[1])
                offset = int(parts[2])
                offsets[partition] = offset
    return offsets


def get_group_offsets(group_id: str) -> dict[int, dict]:
    """Retorna os offsets consumidos por um grupo especifico por particao."""
    cmd = [
        "docker", "exec", KAFKA_CONTAINER,
        "kafka-consumer-groups", "--bootstrap-server", BOOTSTRAP,
        "--describe", "--group", group_id
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    info = {}
    for line in res.stdout.strip().splitlines():
        if not line or line.startswith("GROUP") or "Error" in line:
            continue
        parts = line.split()
        if len(parts) >= 6 and parts[1] == TOPIC:
            try:
                partition = int(parts[2])
                committed = int(parts[3]) if parts[3] != "-" else 0
                log_end = int(parts[4]) if parts[4] != "-" else 0
                lag = int(parts[5]) if parts[5] != "-" else 0
                info[partition] = {
                    "committed": committed,
                    "log_end": log_end,
                    "lag": lag
                }
            except ValueError:
                pass
    return info


def publish_test_orders(count: int = 5) -> int:
    """Publica N pedidos de teste para observar avanço de offset."""
    ok = 0
    for i in range(1, count + 1):
        payload = {
            "customer_id": f"cust-offset-{i}",
            "customer_email": f"offset{i}@test.com",
            "items": [{"product_id": f"prod-off-{i}", "product_name": "Item Offset Test", "quantity": 1, "unit_price": "75.00"}],
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
                ok += 1
        except Exception:
            pass
        time.sleep(0.05)
    return ok


def print_offset_table(title: str, earliest: dict, latest: dict, group_offsets: dict):
    print(f"\n{BOLD}{title}{RESET}")
    print("┌──────────┬──────────┬──────────┬────────────────────────────┬────────────────────────────┐")
    print("│ Partição │ Earliest │ Log-End  │ notification-group (Offset/Lag) │ inventory-group (Offset/Lag)    │")
    print("├──────────┼──────────┼──────────┼────────────────────────────┼────────────────────────────┤")

    partitions = sorted(latest.keys())
    for p in partitions:
        ear = earliest.get(p, 0)
        leo = latest.get(p, 0)

        notif_data = group_offsets["notification-group"].get(p, {})
        notif_off = notif_data.get("committed", "-")
        notif_lag = notif_data.get("lag", 0)

        inv_data = group_offsets["inventory-group"].get(p, {})
        inv_off = inv_data.get("committed", "-")
        inv_lag = inv_data.get("lag", 0)

        notif_str = f"{notif_off} (Lag: {notif_lag})"
        inv_str = f"{inv_off} (Lag: {inv_lag})"

        print(f"│    {p:<5} │ {ear:<8} │ {leo:<8} │ {notif_str:<26} │ {inv_str:<26} │")

    print("└──────────┴──────────┴──────────┴────────────────────────────┴────────────────────────────┘")


def main():
    print(f"\n{BOLD}{'=' * 75}{RESET}")
    print(f"{BOLD}📍 Card 16 — Auditoria e Inspeção de Offsets no Kafka{RESET}")
    print(f"{BOLD}{'=' * 75}{RESET}\n")

    # 1. Coleta inicial
    print(f"{CYAN}[1/3] Mapeando estado inicial das partições do tópico '{TOPIC}'...{RESET}")
    earliest_init = get_log_offsets("-2")
    latest_init = get_log_offsets("-1")
    group_offsets_init = {g: get_group_offsets(g) for g in GROUPS}

    print_offset_table("📊 Estado Inicial dos Offsets", earliest_init, latest_init, group_offsets_init)

    # 2. Publicar lote de mensagens para mover os offsets
    print(f"\n{CYAN}[2/3] Publicando 5 novos eventos no Kafka para mover os ponteiros de offset...{RESET}")
    published = publish_test_orders(5)
    print(f"  ✅ {published}/5 novos eventos produzidos com sucesso.")

    print(f"  Aguardando 2 segundos para consumo e commit de offset...")
    time.sleep(2.5)

    # 3. Coleta após publicação
    print(f"\n{CYAN}[3/3] Mapeando estado dos offsets APÓS a publicação dos novos eventos...{RESET}")
    earliest_post = get_log_offsets("-2")
    latest_post = get_log_offsets("-1")
    group_offsets_post = {g: get_group_offsets(g) for g in GROUPS}

    print_offset_table("📈 Estado Atualizado dos Offsets (Após Produção & Consumo)", earliest_post, latest_post, group_offsets_post)

    # Conclusão didática
    print(f"\n{BOLD}{'=' * 75}{RESET}")
    print(f"{GREEN}{BOLD}💡 Conclusões Arquiteturais sobre Offsets:{RESET}")
    print(f"  1. {BOLD}Independência de Leitura:{RESET} Cada Consumer Group mantém seu próprio ponteiro de")
    print(f"     offset em `__consumer_offsets`. Um consumidor não afeta o progresso do outro.")
    print(f"  2. {BOLD}Idempotência de Avanço:{RESET} À medida que as mensagens são lidas e confirmadas,")
    print(f"     o 'Committed Offset' alcança o 'Log-End-Offset', mantendo o Lag zerado.")
    print(f"  3. {BOLD}Imutabilidade:{RESET} As mensagens continuam armazenadas do 'Earliest' ao 'Log-End'")
    print(f"     mesmo após serem lidas por ambos os grupos.")
    print(f"{BOLD}{'=' * 75}{RESET}\n")


if __name__ == "__main__":
    main()
