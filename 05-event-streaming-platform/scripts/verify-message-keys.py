#!/usr/bin/env python3
# =============================================================================
# scripts/verify-message-keys.py — Valida Message Keys e Ordering por Partição
# =============================================================================
# Card 11 — Implementar Message Keys
#
# Prova que todos os eventos de um mesmo pedido (order_id) sempre caem na
# mesma partição Kafka, independente do tipo de evento ou da quantidade de
# mensagens publicadas.
#
# O que o script faz:
#   1. Cria 3 pedidos distintos via POST /orders
#   2. Atualiza o status de cada pedido 2 vezes via PATCH /orders/{id}/status
#   3. Consome as mensagens dos tópicos orders.created e orders.updated
#   4. Exibe o mapeamento: order_id → partição para cada evento
#   5. Valida: todos os eventos do mesmo order_id estão na MESMA partição
#
# Uso:
#   python3 scripts/verify-message-keys.py
# =============================================================================

import json
import subprocess
import time
import urllib.error
import urllib.request

API_URL = "http://localhost:8000"
KAFKA_CONTAINER = "kafka"
BOOTSTRAP = "kafka:9092"

# Paleta de cores ANSI
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


# =============================================================================
# Helpers HTTP
# =============================================================================

def post(path: str, body: dict) -> dict | None:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{API_URL}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  {RED}❌ POST {path} falhou: {e}{RESET}")
        return None


def patch(path: str, body: dict) -> dict | None:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{API_URL}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  {RED}❌ PATCH {path} falhou: {e}{RESET}")
        return None


# =============================================================================
# Leitura do Kafka via kafka-console-consumer dentro do container
# =============================================================================

def read_kafka_topic(topic: str, max_messages: int = 200, timeout_ms: int = 8000) -> list[dict]:
    """
    Consome mensagens do tópico via kafka-console-consumer.
    Retorna lista de dicts: {order_id, partition, event_type, event_id}
    """
    cmd = [
        "docker", "exec", KAFKA_CONTAINER,
        "kafka-console-consumer",
        "--bootstrap-server", BOOTSTRAP,
        "--topic", topic,
        "--from-beginning",
        f"--max-messages", str(max_messages),
        "--property", "print.key=true",
        "--property", "print.partition=true",
        "--property", "key.separator= | ",
        "--timeout-ms", str(timeout_ms),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=timeout_ms // 1000 + 5
        )
        messages = []
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line or "|" not in line:
                continue
            parts = line.split(" | ", 2)
            if len(parts) < 3:
                continue
            partition_str, key, payload_str = parts
            # Extrai número da partição ex: "Partition:2"
            partition = int(partition_str.replace("Partition:", "").strip())
            try:
                payload = json.loads(payload_str)
                messages.append({
                    "order_id": key.strip(),
                    "partition": partition,
                    "event_type": payload.get("event_type", "?"),
                    "event_id": payload.get("event_id", "?"),
                })
            except json.JSONDecodeError:
                continue
        return messages
    except Exception as e:
        print(f"  {RED}❌ Erro ao ler tópico {topic}: {e}{RESET}")
        return []


# =============================================================================
# Main
# =============================================================================

def main():
    print(f"\n{BOLD}{'=' * 66}{RESET}")
    print(f"{BOLD}🔑  Card 11 — Validação de Message Keys no Kafka{RESET}")
    print(f"{BOLD}{'=' * 66}{RESET}\n")

    # ── 1. Criar pedidos ──────────────────────────────────────────────────
    print(f"{CYAN}[1/3] Criando 3 pedidos via POST /orders...{RESET}")

    orders_data = [
        {"customer_id": "c-key-01", "customer_email": "alice@test.com",
         "items": [{"product_id": "p-1", "product_name": "Notebook", "quantity": 1, "unit_price": "3999.00"}],
         "currency": "BRL"},
        {"customer_id": "c-key-02", "customer_email": "bob@test.com",
         "items": [{"product_id": "p-2", "product_name": "Mouse", "quantity": 2, "unit_price": "149.90"}],
         "currency": "BRL"},
        {"customer_id": "c-key-03", "customer_email": "carol@test.com",
         "items": [{"product_id": "p-3", "product_name": "Teclado", "quantity": 1, "unit_price": "299.00"}],
         "currency": "BRL"},
    ]

    created_orders = []
    for body in orders_data:
        result = post("/orders", body)
        if result:
            oid = result["order_id"]
            created_orders.append(oid)
            print(f"  ✅ Pedido criado: {oid[:16]}... ({body['customer_email']})")
        time.sleep(0.3)

    if not created_orders:
        print(f"{RED}Nenhum pedido criado. A API está no ar?{RESET}")
        return

    # ── 2. Atualizar status de cada pedido 2 vezes ────────────────────────
    print(f"\n{CYAN}[2/3] Atualizando status de cada pedido 2x via PATCH...{RESET}")
    status_sequence = ["confirmed", "processing"]

    for order_id in created_orders:
        for status in status_sequence:
            result = patch(f"/orders/{order_id}/status", {"new_status": status, "reason": "Card 11 test"})
            if result:
                print(f"  ✅ {order_id[:16]}... → {status}")
            time.sleep(0.2)

    # ── 3. Aguardar propagação e ler os tópicos ───────────────────────────
    print(f"\n{CYAN}[3/3] Lendo mensagens dos tópicos (aguardando propagação)...{RESET}")
    time.sleep(3)

    all_messages = {}  # order_id → list of {partition, event_type}

    for topic in ["orders.created", "orders.updated"]:
        messages = read_kafka_topic(topic, max_messages=100, timeout_ms=5000)
        for msg in messages:
            oid = msg["order_id"]
            if oid not in all_messages:
                all_messages[oid] = []
            all_messages[oid].append({
                "partition": msg["partition"],
                "event_type": msg["event_type"],
                "topic": topic,
            })

    # ── Resultado: apenas os pedidos criados nesta sessão ─────────────────
    print(f"\n{BOLD}{'=' * 66}{RESET}")
    print(f"{BOLD}📊  Resultado da Validação{RESET}")
    print(f"{BOLD}{'=' * 66}{RESET}\n")

    all_ok = True
    for order_id in created_orders:
        events = all_messages.get(order_id, [])
        partitions = set(e["partition"] for e in events)

        if not events:
            print(f"  {YELLOW}⚠️  {order_id[:16]}...  → sem eventos encontrados{RESET}")
            continue

        consistent = len(partitions) == 1
        if not consistent:
            all_ok = False

        icon = f"{GREEN}✅" if consistent else f"{RED}❌"
        partition_n = list(partitions)[0] if consistent else f"INCONSISTENTE {partitions}"

        print(f"  {icon}  order_id: {order_id[:16]}...{RESET}")
        print(f"       Partição fixa:  {BOLD}Partition {partition_n}{RESET}")
        print(f"       Eventos:        {len(events)}")
        for e in events:
            print(f"         • {e['topic']:<20}  {e['event_type']:<15}  → Partition {e['partition']}")
        print()

    print(f"{BOLD}{'=' * 66}{RESET}")
    if all_ok:
        print(f"{GREEN}{BOLD}✅  VALIDAÇÃO APROVADA!{RESET}")
        print(f"  Todos os eventos de cada pedido foram gravados na MESMA partição.")
        print(f"  A Message Key (order_id) está funcionando corretamente.")
    else:
        print(f"{RED}{BOLD}❌  VALIDAÇÃO FALHOU!{RESET}")
        print(f"  Eventos do mesmo pedido foram para partições diferentes.")
    print(f"{BOLD}{'=' * 66}{RESET}\n")


if __name__ == "__main__":
    main()
