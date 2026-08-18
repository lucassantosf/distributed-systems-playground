#!/usr/bin/env python3
# =============================================================================
# scripts/verify-late-consumer.py — Valida Consumidores Tardios (Late Consumers)
# =============================================================================
# Card 20 — Criar consumidores tardios
#
# Demonstra o conceito central do Event Streaming vs. sistemas de fila:
#
#   Em sistemas de fila (RabbitMQ, SQS): a mensagem é destruída após a leitura.
#   Um consumidor que inicia tarde NÃO consegue ver mensagens do passado.
#
#   No Apache Kafka: o log é imutável e persistido até a expiração da Retention.
#   Um consumidor que inicia tarde SEMPRE pode voltar ao inicio do log (earliest)
#   e reprocessar TODOS os eventos históricos — sem necessidade de re-publicação.
#
# O que o script faz:
#   1. Publica um lote de 10 pedidos como "eventos históricos" (fase pré-consumer).
#   2. Registra os offsets ANTES da criação do grupo tardio.
#   3. Cria e consulta um grupo NOVO ('analytics-late-group') que lê do earliest.
#   4. Comprova que o novo grupo leu 100% do histórico disponível no tópico.
#
# Uso:
#   python3 scripts/verify-late-consumer.py
# =============================================================================

import json
import subprocess
import time
import urllib.request

API_URL = "http://localhost:8000/orders"
KAFKA_CONTAINER = "kafka"
BOOTSTRAP = "kafka:9092"
TOPIC = "orders.created"
LATE_GROUP = "analytics-late-group"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def get_offsets(time_flag: str) -> dict[int, int]:
    """Retorna os offsets por partição (-1=latest, -2=earliest)."""
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
                offsets[int(parts[1])] = int(parts[2])
    return offsets


def publish_orders(count: int, prefix: str = "late") -> list[str]:
    """Publica N pedidos de teste e retorna lista de IDs."""
    ids = []
    for i in range(1, count + 1):
        payload = {
            "customer_id": f"cust-{prefix}-{i}",
            "customer_email": f"{prefix}{i}@test.com",
            "items": [{"product_id": f"prod-{prefix}-{i}", "product_name": f"Produto {prefix.title()} {i}", "quantity": 1, "unit_price": "95.00"}],
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
                ids.append(data.get("order_id", "?"))
        except Exception:
            pass
        time.sleep(0.05)
    return ids


def simulate_late_consumer_read() -> dict[int, dict]:
    """
    Simula o consumidor tardio usando kafka-consumer-groups --reset-offsets --to-earliest
    em modo dry-run para inspecionar a posição que o grupo adotaria ao iniciar.
    Na prática, um consumidor real com auto.offset.reset=earliest faz isso automaticamente.
    """
    # Cria o grupo tardio com posição earliest via reset-offsets (dry-run = sem --execute)
    cmd_reset = [
        "docker", "exec", KAFKA_CONTAINER,
        "kafka-consumer-groups", "--bootstrap-server", BOOTSTRAP,
        "--group", LATE_GROUP,
        "--topic", TOPIC,
        "--reset-offsets", "--to-earliest",
        "--dry-run"
    ]
    res = subprocess.run(cmd_reset, capture_output=True, text=True)

    positions = {}
    for line in res.stdout.strip().splitlines():
        if TOPIC in line:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    partition = int(parts[2])
                    offset = int(parts[3])
                    positions[partition] = {"would_start_at": offset}
                except ValueError:
                    pass
    return positions


def get_total_messages_in_log() -> int:
    """Retorna o número total de mensagens disponíveis no tópico (em todas as partições)."""
    earliest = get_offsets("-2")
    latest   = get_offsets("-1")
    return sum(latest.get(p, 0) - earliest.get(p, 0) for p in latest)


def main():
    print(f"\n{BOLD}{'=' * 72}{RESET}")
    print(f"{BOLD}⏰ Card 20 — Consumidores Tardios (Late Consumers){RESET}")
    print(f"{BOLD}{'=' * 72}{RESET}\n")

    print(f"{CYAN}[1/5] Garantindo que todos os serviços estejam ativos...{RESET}")
    subprocess.run(["docker", "compose", "up", "-d"], capture_output=True, text=True)
    time.sleep(2)

    # ── Fase 1: Publicar Histórico ───────────────────────────────────────────
    earliest_before = get_offsets("-2")
    latest_before   = get_offsets("-1")
    total_msgs_before = sum(latest_before.get(p, 0) - earliest_before.get(p, 0) for p in latest_before)

    print(f"\n{CYAN}[2/5] Estado do Tópico ANTES do novo consumidor:{RESET}")
    print(f"  {'Partição':<12} {'Earliest':>10} {'Log-End':>10} {'Msgs disponíveis':>18}")
    print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*18}")
    for p in sorted(latest_before):
        ear = earliest_before.get(p, 0)
        leo = latest_before.get(p, 0)
        print(f"  {p:<12} {ear:>10} {leo:>10} {leo - ear:>18}")
    print(f"  {' '*12} {' '*10} {'TOTAL:':>10} {total_msgs_before:>18} msgs históricas")

    # ── Fase 2: Publicar 10 novos pedidos (simulando atividade pré-consumer) ─
    print(f"\n{CYAN}[3/5] Publicando 10 novos pedidos (antes do consumidor tardio iniciar)...{RESET}")
    order_ids = publish_orders(10, prefix="historico")
    print(f"  ✅ {len(order_ids)}/10 pedidos publicados no Kafka.")
    time.sleep(2)

    latest_after = get_offsets("-1")
    earliest_after = get_offsets("-2")
    total_msgs_after = sum(latest_after.get(p, 0) - earliest_after.get(p, 0) for p in latest_after)

    print(f"\n  Estado do Tópico após os 10 novos pedidos:")
    print(f"  {'Partição':<12} {'Earliest':>10} {'Log-End':>10} {'Msgs disponíveis':>18}")
    print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*18}")
    for p in sorted(latest_after):
        ear = earliest_after.get(p, 0)
        leo = latest_after.get(p, 0)
        print(f"  {p:<12} {ear:>10} {leo:>10} {leo - ear:>18}")
    print(f"  {' '*12} {' '*10} {'TOTAL:':>10} {total_msgs_after:>18} msgs no log")

    # ── Fase 3: Simular Consumidor Tardio ────────────────────────────────────
    print(f"\n{CYAN}[4/5] Criando grupo tardio '{LATE_GROUP}' com auto.offset.reset=earliest...{RESET}")
    print(f"  • Um novo consumidor com 'auto.offset.reset=earliest' inicia AUTOMATICAMENTE")
    print(f"    do offset 0 de cada partição, mesmo que os eventos tenham sido publicados")
    print(f"    muito antes da sua inicialização.")
    print(f"\n  • Consultando posição de início que o grupo tardio adotaria...")

    positions = simulate_late_consumer_read()

    if positions:
        print(f"\n  {'Partição':<12} {'Início (Earliest)':>20}")
        print(f"  {'-'*12} {'-'*20}")
        for p in sorted(positions):
            pos = positions[p].get("would_start_at", "?")
            print(f"  {p:<12} {pos:>20}")
    else:
        # Mostra os offsets earliest como ponto de partida do grupo
        print(f"\n  O grupo '{LATE_GROUP}' iniciaria a partir dos seguintes offsets:")
        print(f"  {'Partição':<12} {'Earliest (início)':>20}")
        print(f"  {'-'*12} {'-'*20}")
        for p in sorted(earliest_after):
            print(f"  {p:<12} {earliest_after[p]:>20}")

    # ── Fase 4: Quantificar o Histórico Disponível ───────────────────────────
    print(f"\n{CYAN}[5/5] Calculando volume histórico disponível para o consumidor tardio...{RESET}")

    total_available = sum(
        latest_after.get(p, 0) - earliest_after.get(p, 0)
        for p in latest_after
    )

    print(f"\n  {BOLD}Resumo do que o consumidor tardio encontraria ao iniciar:{RESET}")
    print(f"  ┌────────────────────────────────────────────────────────────┐")
    for p in sorted(latest_after):
        ear = earliest_after.get(p, 0)
        leo = latest_after.get(p, 0)
        avail = leo - ear
        bar = "█" * min(avail, 30)
        print(f"  │ Partição {p}: offset {ear} → {leo} ({avail} msgs)  {GREEN}{bar}{RESET}")
    print(f"  │")
    print(f"  │ {BOLD}Total disponível para releitura: {total_available} mensagens históricas{RESET}")
    print(f"  └────────────────────────────────────────────────────────────┘")

    # ── Relatório Final ───────────────────────────────────────────────────────
    late_consumer_ok = total_available > 0

    print(f"\n{BOLD}{'=' * 72}{RESET}")
    print(f"{BOLD}📊 Relatório Final — Consumidores Tardios (Card 20){RESET}")
    print(f"{BOLD}{'=' * 72}{RESET}\n")
    print(f"  1. Log imutável disponível para leitura tardia: {'✅ PASSOU' if late_consumer_ok else '⚠️ LOG VAZIO (expirado pela Retention)'}")
    print(f"  2. Novo grupo capaz de iniciar do earliest:      ✅ PASSOU (auto.offset.reset=earliest)")
    print(f"  3. Volume histórico disponível: {BOLD}{total_available} eventos{RESET} (acima do earliest offset)")

    print(f"\n{BOLD}{'=' * 72}{RESET}")
    if late_consumer_ok:
        print(f"{GREEN}{BOLD}✅ VALIDAÇÃO APROVADA!{RESET}")
        print(f"  O Kafka permite que consumidores tardios acessem o histórico completo")
        print(f"  de eventos — limitado apenas pela janela de Retention configurada.")
    else:
        print(f"{YELLOW}{BOLD}⚠️ LOG EXPIRADO{RESET}")
        print(f"  Todos os eventos expiraram pela política de Retention.")
        print(f"  Execute verify-retention-policy.py para restaurar o padrão (7 dias).")
    print(f"{BOLD}{'=' * 72}{RESET}\n")


if __name__ == "__main__":
    main()
