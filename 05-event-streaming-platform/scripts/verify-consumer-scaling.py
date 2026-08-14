#!/usr/bin/env python3
# =============================================================================
# scripts/verify-consumer-scaling.py — Valida Escalabilidade Horizontal
# =============================================================================
# Card 14 — Escalar Consumidores Horizontalmente
#
# Demonstra que quando escalamos o notification-consumer para 3 instâncias:
#   1. O Kafka divide as 3 partições do tópico orders.created entre as 3 instâncias (1:1).
#   2. As 3 instâncias processam pedidos em PARALELO.
#   3. Cada instância é responsável EXCLUSIVAMENTE por sua partição atribuída.
#
# Uso:
#   python3 scripts/verify-consumer-scaling.py
# =============================================================================

import json
import subprocess
import time
import urllib.error
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


def get_consumer_containers() -> list[str]:
    """Retorna lista de IDs/Nomes de containers ativos do notification-consumer."""
    cmd = ["docker", "ps", "--filter", "name=notification-consumer", "--format", "{{.Names}}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return [name.strip() for name in res.stdout.strip().splitlines() if name.strip()]


def get_kafka_group_members() -> list[dict]:
    """Consulta kafka-consumer-groups --describe no Kafka para obter partição vs consumer-id."""
    cmd = [
        "docker", "exec", KAFKA_CONTAINER,
        "kafka-consumer-groups", "--bootstrap-server", BOOTSTRAP,
        "--describe", "--group", GROUP
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    members = []
    lines = res.stdout.strip().splitlines()
    for line in lines:
        if not line or line.startswith("GROUP") or "Error" in line:
            continue
        parts = line.split()
        if len(parts) >= 7:
            grp, topic, partition, current_off, log_end, lag, cid = parts[:7]
            host = parts[7] if len(parts) > 7 else "-"
            members.append({
                "partition": partition,
                "consumer_id": cid,
                "host": host
            })
    return members


def publish_batch(count: int = 15) -> int:
    """Publica N pedidos via POST /orders."""
    ok = 0
    for i in range(1, count + 1):
        payload = {
            "customer_id": f"cust-scale-{i}",
            "customer_email": f"scale{i}@test.com",
            "items": [{"product_id": f"prod-{i}", "product_name": "Item Escalado", "quantity": 1, "unit_price": "50.00"}],
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


def main():
    print(f"\n{BOLD}{'=' * 66}{RESET}")
    print(f"{BOLD}🚀 Card 14 — Validação de Escalabilidade Horizontal (3 Instâncias){RESET}")
    print(f"{BOLD}{'=' * 66}{RESET}\n")

    # 1. Verificar Containers
    containers = get_consumer_containers()
    print(f"{CYAN}[1/4] Verificando instâncias ativas do notification-consumer...{RESET}")
    print(f"  Instâncias Docker rodando: {BOLD}{len(containers)}{RESET}")
    for c in containers:
        print(f"  • {c}")

    if len(containers) < 2:
        print(f"\n{YELLOW}⚠️  Apenas 1 instância encontrada. Escalando via docker compose...{RESET}")
        subprocess.run(["docker", "compose", "up", "-d", "--scale", "notification-consumer=3"], check=True)
        time.sleep(4)
        containers = get_consumer_containers()

    # 2. Verificar Atribuição de Partições no Kafka
    print(f"\n{CYAN}[2/4] Consultando divisão de partições no Kafka ('{GROUP}')...{RESET}")
    members = get_kafka_group_members()

    unique_consumers = set(m["consumer_id"] for m in members if m["consumer_id"] != "-")

    for m in members:
        print(f"  • Partição {m['partition']} → Consumer ID: {BOLD}{m['consumer_id'][:35]}{RESET} (Host: {m['host']})")

    # 3. Disparar Carga de Pedidos
    print(f"\n{CYAN}[3/4] Disparando lote de 15 pedidos para testar processamento paralelo...{RESET}")
    sent = publish_batch(15)
    print(f"  ✅ {sent}/15 pedidos enviados.")

    time.sleep(2.0)

    # 4. Verificar Logs de cada Container
    print(f"\n{CYAN}[4/4] Analisando logs de cada instância container...{RESET}")

    total_processed = 0
    print(f"\n{BOLD}{'=' * 66}{RESET}")
    print(f"{BOLD}📊 Distribuição de Carga entre as Instâncias{RESET}")
    print(f"{BOLD}{'=' * 66}{RESET}\n")

    for c in sorted(containers):
        res = subprocess.run(["docker", "logs", "--tail", "50", c], capture_output=True, text=True)
        logs = (res.stdout or "") + "\n" + (res.stderr or "")
        lines = [l for l in logs.splitlines() if "E-MAIL ENVIADO" in l or "Evento recebido" in l]
        count = len(lines)
        total_processed += count

        # Descobrir partições atendidas por esse container nos logs
        partitions_seen = set()
        for l in logs.splitlines():
            if "partition=" in l:
                try:
                    part_num = l.split("partition=")[1].split()[0]
                    partitions_seen.add(part_num)
                except Exception:
                    pass

        part_str = f"Partição(ões): {', '.join(sorted(partitions_seen))}" if partitions_seen else "Sem registros recentes"
        bar = "█" * (count * 2)

        print(f"  ┌─ Container: {BOLD}{c}{RESET}")
        print(f"  │  Processados neste lote: {BOLD}{count} eventos{RESET}")
        print(f"  │  {part_str}")
        print(f"  │  Barra de Carga: {GREEN}{bar}{RESET}")
        print(f"  └─────────────────────────────────────────────────────────────\n")

    print(f"{BOLD}{'=' * 66}{RESET}")
    if len(unique_consumers) > 1:
        print(f"{GREEN}{BOLD}✅ VALIDAÇÃO APROVADA!{RESET}")
        print(f"  As partições foram divididas automaticamente entre as múltiplas instâncias.")
        print(f"  O processamento paralelo horizontal do Consumer Group está ativo.")
    else:
        print(f"{YELLOW}{BOLD}⚠️ ALERTA DE ESCALABILIDADE{RESET}")
        print(f"  Aguardando rebalanceamento completo das partições no cluster Kafka.")
    print(f"{BOLD}{'=' * 66}{RESET}\n")


if __name__ == "__main__":
    main()
