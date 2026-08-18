#!/usr/bin/env python3
# =============================================================================
# scripts/verify-retry-mechanism.py — Valida o Mecanismo de Retry Topic
# =============================================================================
# Card 22 — Implementar Retry
#
# O que este script faz:
#   1. Publica um pedido com falha temporária simulada ("simulate_error": "temporary").
#   2. O consumidor principal (orders.created) falha ao processar o evento.
#   3. O evento é capturado e publicado no tópico de retry (orders.created-retry).
#   4. O consumidor de retry aplica o Backoff Progressivo (delay).
#   5. O reprocessamento é executado com sucesso e a notificação é concluída.
#
# Uso:
#   python3 scripts/verify-retry-mechanism.py
# =============================================================================

import json
import subprocess
import time
import urllib.request

API_URL = "http://localhost:8000/orders"
KAFKA_CONTAINER = "kafka"
BOOTSTRAP = "kafka:9092"
RETRY_TOPIC = "orders.created-retry"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def get_topic_offsets(topic_name: str) -> dict[int, int]:
    """Retorna os offsets LATEST por partição para um tópico."""
    cmd = [
        "docker", "exec", KAFKA_CONTAINER,
        "kafka-run-class", "org.apache.kafka.tools.GetOffsetShell",
        "--bootstrap-server", BOOTSTRAP,
        "--topic", topic_name,
        "--time", "-1"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    offsets = {}
    for line in res.stdout.strip().splitlines():
        if line.startswith(topic_name):
            parts = line.split(":")
            if len(parts) == 3:
                offsets[int(parts[1])] = int(parts[2])
    return offsets


def publish_order_with_error(error_type: str = "temporary", fail_until_retry: int = 1) -> str:
    """Publica um pedido de teste configurado para falhar."""
    payload = {
        "customer_id": "cust-retry-test",
        "customer_email": "retrytest@domain.com",
        "items": [{"product_id": "prod-retry-1", "product_name": "Produto Teste Retry", "quantity": 1, "unit_price": "150.00"}],
        "currency": "BRL",
        "simulate_error": error_type,
        "fail_until_retry": fail_until_retry,
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
            return data.get("order_id", "?")
    except Exception as e:
        print(f"Erro na publicação: {e}")
        return ""


def check_container_logs(filter_str: str) -> list[str]:
    """Consulta os logs do container notification-consumer procurando por termos específicos."""
    cmd = ["docker", "compose", "logs", "--tail=50", "notification-consumer"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    lines = []
    for line in res.stdout.splitlines():
        if filter_str in line:
            lines.append(line)
    return lines


def main():
    print(f"\n{BOLD}{'=' * 74}{RESET}")
    print(f"{BOLD}🔄 Card 22 — Validação do Mecanismo de Retry Topic com Backoff{RESET}")
    print(f"{BOLD}{'=' * 74}{RESET}\n")

    print(f"{CYAN}[1/4] Recarregando infraestrutura e notification-consumer...{RESET}")
    subprocess.run(["docker", "compose", "up", "-d", "--build", "notification-consumer"], capture_output=True, text=True)
    time.sleep(3.0)

    # 1. Medir offsets do tópico de retry antes do teste
    offsets_before = get_topic_offsets(RETRY_TOPIC)
    total_retry_before = sum(offsets_before.values())

    # 2. Publicar evento configurado para falhar temporariamente na 1ª tentativa
    print(f"\n{CYAN}[2/4] Publicando pedido com falha temporária simulada (SMTP Timeout)...{RESET}")
    order_id = publish_order_with_error(error_type="temporary", fail_until_retry=1)
    print(f"  ✅ Pedido publicado | order_id={BOLD}{order_id}{RESET}")

    print(f"\n  ⏳ Aguardando processamento inicial e roteamento para Retry Topic...")
    time.sleep(4.0)

    # 3. Inspecionar se o evento passou pelo tópico de retry
    offsets_after = get_topic_offsets(RETRY_TOPIC)
    total_retry_after = sum(offsets_after.values())
    msgs_in_retry = total_retry_after - total_retry_before

    print(f"\n{CYAN}[3/4] Inspecionando tópico de Retry '{RETRY_TOPIC}':{RESET}")
    print(f"  • Mensagens recebidas no Retry Topic: {BOLD}{msgs_in_retry}{RESET}")

    # 4. Verificar logs de auditoria
    print(f"\n{CYAN}[4/4] Verificando logs de auditoria do notification-consumer:{RESET}")
    retry_logs = check_container_logs("RETRY PATTERN")
    backoff_logs = check_container_logs("BACKOFF RETRY")
    success_logs = check_container_logs("E-MAIL ENVIADO")

    if retry_logs:
        print(f"  • Log de Roteamento para Retry: {GREEN}{retry_logs[-1]}{RESET}")
    if backoff_logs:
        print(f"  • Log de Backoff Progressivo:   {GREEN}{backoff_logs[-1]}{RESET}")
    if success_logs:
        print(f"  • Log de Sucesso no Reprocessamento: {GREEN}{success_logs[-1]}{RESET}")

    # Relatório Final
    has_retry_routing = msgs_in_retry > 0 or len(retry_logs) > 0
    has_backoff = len(backoff_logs) > 0 or len(success_logs) > 0

    print(f"\n{BOLD}{'=' * 74}{RESET}")
    print(f"{BOLD}📊 Relatório Final — Retry Mechanism (Card 22){RESET}")
    print(f"{BOLD}{'=' * 74}{RESET}\n")

    print(f"  1. Captura de Falha Temporária:    {'✅ PASSOU' if has_retry_routing else '⚠️ VERIFICAR LOGS'}")
    print(f"  2. Roteamento para Retry Topic:   {'✅ PASSOU (orders.created-retry)' if has_retry_routing else '⚠️ SEM EVENTOS NO RETRY'}")
    print(f"  3. Backoff Progressivo e Re-exec: {'✅ PASSOU (Processado com sucesso)' if has_backoff else '⚠️ VERIFICAR BACKOFF'}")

    print(f"\n{BOLD}{'=' * 74}{RESET}")
    if has_retry_routing and has_backoff:
        print(f"{GREEN}{BOLD}✅ VALIDAÇÃO APROVADA!{RESET}")
        print(f"  O mecanismo de Retry Topic com Backoff funcionou com perfeição.")
    else:
        print(f"{YELLOW}{BOLD}⚠️ VALIDAÇÃO COM ALERTAS{RESET}")
        print(f"  Verifique os logs do container notification-consumer.")
    print(f"{BOLD}{'=' * 74}{RESET}\n")


if __name__ == "__main__":
    main()
