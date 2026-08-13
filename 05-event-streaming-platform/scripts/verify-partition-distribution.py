#!/usr/bin/env python3
# =============================================================================
# scripts/verify-partition-distribution.py — Valida Distribuição de Partições
# =============================================================================
# Card 12 — Validar distribuição das mensagens
#
# Demonstra estatisticamente que o particionador do Kafka (MurmurHash2)
# distribui mensagens com chaves diferentes (order_id) de forma equilibrada
# entre todas as partições do tópico, evitando Hot Partitions.
#
# O que o script faz:
#   1. Registra os offsets iniciais de cada partição do tópico orders.created
#   2. Publica N pedidos fictícios (padrão: 30) via POST /orders
#   3. Registra os offsets finais e calcula a quantidade de mensagens por partição
#   4. Exibe relatório estatístico com porcentagens e diagnóstico de equilíbrio
#
# Uso:
#   python3 scripts/verify-partition-distribution.py           # 30 pedidos (padrão)
#   python3 scripts/verify-partition-distribution.py --count 60 # 60 pedidos
# =============================================================================

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
import uuid

API_URL = "http://localhost:8000/orders"
KAFKA_CONTAINER = "kafka"
BOOTSTRAP = "kafka:9092"
TOPIC = "orders.created"

# Paleta de cores ANSI
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def get_partition_offsets(topic: str) -> dict[int, int]:
    """
    Obtém os offsets atuais (LOG-END-OFFSET) por partição para o tópico fornecido
    utilizando a ferramenta GetOffsetShell do Kafka.
    """
    cmd = [
        "docker", "exec", KAFKA_CONTAINER,
        "kafka-run-class", "org.apache.kafka.tools.GetOffsetShell",
        "--bootstrap-server", BOOTSTRAP,
        "--topic", topic
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        offsets = {}
        for line in res.stdout.strip().splitlines():
            # Formato: topic:partition:offset
            parts = line.strip().split(":")
            if len(parts) == 3:
                partition = int(parts[1])
                offset = int(parts[2])
                offsets[partition] = offset
        return offsets
    except Exception as e:
        print(f"{RED}❌ Erro ao buscar offsets do tópico {topic}: {e}{RESET}")
        return {}


def publish_order(idx: int, total: int) -> bool:
    payload = {
        "customer_id": f"cust-dist-{uuid.uuid4().hex[:6]}",
        "customer_email": f"user{idx}@dist test.com",
        "items": [
            {"product_id": f"prod-{idx}", "product_name": "Item Teste Distribuição", "quantity": 1, "unit_price": "100.00"}
        ],
        "currency": "BRL"
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res_json = json.loads(resp.read())
            return res_json.get("event_published", False)
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Validação de Distribuição de Partições (Card 12)")
    parser.add_argument("--count", type=int, default=30, help="Quantidade de mensagens a enviar (padrão: 30)")
    args = parser.parse_args()

    print(f"\n{BOLD}{'=' * 66}{RESET}")
    print(f"{BOLD}📊 Card 12 — Validação de Distribuição entre Partições Kafka{RESET}")
    print(f"{BOLD}{'=' * 66}{RESET}\n")

    # 1. Offsets Iniciais
    print(f"{CYAN}[1/3] Obtendo contagem inicial de mensagens em '{TOPIC}'...{RESET}")
    initial_offsets = get_partition_offsets(TOPIC)
    if not initial_offsets:
        print(f"{RED}Não foi possível ler as partições. Verifique se o Kafka está ativo.{RESET}")
        return

    for part, off in sorted(initial_offsets.items()):
        print(f"  • Partição {part}: {off} mensagens acumuladas")

    # 2. Publicação em Lote
    print(f"\n{CYAN}[2/3] Publicando {args.count} novos pedidos via API...{RESET}")
    success_count = 0
    for i in range(1, args.count + 1):
        if publish_order(i, args.count):
            success_count += 1
        time.sleep(0.05)

    print(f"  ✅ {success_count}/{args.count} pedidos publicados com sucesso.")

    # 3. Offsets Finais & Cálculo do Delta
    print(f"\n{CYAN}[3/3] Analisando a distribuição do novo lote entre as partições...{RESET}")
    time.sleep(1.5)  # Pequena pausa para consolidação de offsets no broker
    final_offsets = get_partition_offsets(TOPIC)

    deltas = {}
    total_new_messages = 0
    for part in initial_offsets.keys():
        init_off = initial_offsets.get(part, 0)
        fin_off = final_offsets.get(part, 0)
        new_msgs = fin_off - init_off
        deltas[part] = new_msgs
        total_new_messages += new_msgs

    print(f"\n{BOLD}{'=' * 66}{RESET}")
    print(f"{BOLD}📈 Relatório Estatístico de Distribuição{RESET}")
    print(f"{BOLD}{'=' * 66}{RESET}\n")

    expected_per_partition = total_new_messages / len(deltas) if deltas else 0

    print(f"  Total de Mensagens do Lote: {BOLD}{total_new_messages}{RESET}")
    print(f"  Média Esperada por Partição: {BOLD}{expected_per_partition:.1f}{RESET}\n")

    is_balanced = True
    for part in sorted(deltas.keys()):
        count = deltas[part]
        pct = (count / total_new_messages * 100) if total_new_messages > 0 else 0.0

        # Alerta se uma partição receber < 15% ou > 55% do tráfego em lote moderado
        if pct > 60.0 or (total_new_messages >= 15 and count == 0):
            is_balanced = False
            status = f"{RED}⚠️ Desequilibrado (Hot Partition?){RESET}"
        else:
            status = f"{GREEN}✅ Equilibrado{RESET}"

        bar_len = int(pct / 4)
        bar = "█" * bar_len

        print(f"  Partição {part}: {BOLD}{count:>3} msg{RESET} ({pct:>5.1f}%) | {CYAN}{bar:<25}{RESET} | {status}")

    print(f"\n{BOLD}{'=' * 66}{RESET}")
    if is_balanced and total_new_messages > 0:
        print(f"{GREEN}{BOLD}✅ VALIDAÇÃO APROVADA!{RESET}")
        print(f"  O particionador distribuiu as mensagens com sucesso entre todas as partições.")
        print(f"  Nenhuma 'Hot Partition' detectada.")
    else:
        print(f"{YELLOW}{BOLD}⚠️ ALERTA DE DISTRIBUIÇÃO{RESET}")
        print(f"  Verifique o desvio das mensagens entre as partições.")
    print(f"{BOLD}{'=' * 66}{RESET}\n")


if __name__ == "__main__":
    main()
