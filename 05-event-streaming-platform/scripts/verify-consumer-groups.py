#!/usr/bin/env python3
# =============================================================================
# scripts/verify-consumer-groups.py — Valida Concorrência de Consumer Groups
# =============================================================================
# Card 13 — Criar Consumer Groups
#
# Prova o padrão Publish-Subscribe (Fan-Out) do Kafka:
#   1. Publica 1 novo pedido via POST /orders
#   2. Consulta db_notification (notification-group)
#   3. Consulta db_inventory (inventory-group)
#   4. Valida: AMBOS os consumidores independentes receberam o mesmo evento
#      e registraram o processamento nos seus respectivos bancos isolados.
#
# Uso:
#   python3 scripts/verify-consumer-groups.py
# =============================================================================

import json
import subprocess
import time
import urllib.error
import urllib.request

API_URL = "http://localhost:8000/orders"
POSTGRES_CONTAINER = "postgres"

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def query_db(db_name: str, sql: str) -> str:
    """Executa consulta SQL no container PostgreSQL e retorna o stdout."""
    cmd = [
        "docker", "exec", POSTGRES_CONTAINER,
        "psql", "-U", "postgres", "-d", db_name, "-t", "-A", "-c", sql
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception as e:
        return ""


def main():
    print(f"\n{BOLD}{'=' * 66}{RESET}")
    print(f"{BOLD}👥 Card 13 — Validação de Consumer Groups Independentes (Fan-Out){RESET}")
    print(f"{BOLD}{'=' * 66}{RESET}\n")

    # 1. Publicar um pedido de teste
    print(f"{CYAN}[1/3] Publicando novo pedido via API POST /orders...{RESET}")
    payload = {
        "customer_id": "cust-group-test",
        "customer_email": "fanout@test.com",
        "items": [
            {"product_id": "p-fanout-01", "product_name": "Teclado Sem Fio", "quantity": 2, "unit_price": "250.00"}
        ],
        "currency": "BRL"
    }

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            order_id = data.get("order_id")
            event_id = data.get("event_id")
            print(f"  ✅ Pedido Criado: {order_id}")
            print(f"  ✅ Event ID:       {event_id}")
    except Exception as e:
        print(f"{RED}❌ Erro ao publicar pedido: {e}{RESET}")
        return

    # 2. Aguardar tempo de consumo do Kafka
    print(f"\n{CYAN}[2/3] Aguardando consumo pelos Consumer Groups (notification-group & inventory-group)...{RESET}")
    time.sleep(2.5)

    # 3. Verificar db_notification
    print(f"\n{CYAN}[3/3] Auditando registros nos bancos de dados dedicados...{RESET}")

    notif_sql = f"SELECT id, customer_email, message FROM notifications WHERE order_id = '{order_id}';"
    notif_res = query_db("db_notification", notif_sql)

    inv_sql = f"SELECT id, product_id, product_name, quantity_reserved, status FROM inventory_reservations WHERE order_id = '{order_id}';"
    inv_res = query_db("db_inventory", inv_sql)

    print(f"\n{BOLD}{'=' * 66}{RESET}")
    print(f"{BOLD}📊 Relatório de Processamento por Consumer Group{RESET}")
    print(f"{BOLD}{'=' * 66}{RESET}\n")

    notif_ok = bool(notif_res)
    inv_ok = bool(inv_res)

    print(f"  ┌─ Consumer Group 1: {BOLD}notification-group{RESET} (db_notification)")
    if notif_ok:
        parts = notif_res.split("|")
        print(f"  │  Status: {GREEN}✅ PROCESSADO COM SUCESSO{RESET}")
        print(f"  │  E-mail enviado para: {parts[1] if len(parts)>1 else 'N/A'}")
    else:
        print(f"  │  Status: {RED}❌ NÃO ENCONTRADO{RESET}")
    print("  └─────────────────────────────────────────────────────────────\n")

    print(f"  ┌─ Consumer Group 2: {BOLD}inventory-group{RESET} (db_inventory)")
    if inv_ok:
        parts = inv_res.split("|")
        print(f"  │  Status: {GREEN}✅ PROCESSADO COM SUCESSO{RESET}")
        print(f"  │  Reserva: {parts[2]} ({parts[1]}) | Qtd: {parts[3]} | Status: {parts[4]}")
    else:
        print(f"  │  Status: {RED}❌ NÃO ENCONTRADO{RESET}")
    print("  └─────────────────────────────────────────────────────────────\n")

    print(f"{BOLD}{'=' * 66}{RESET}")
    if notif_ok and inv_ok:
        print(f"{GREEN}{BOLD}✅ VALIDAÇÃO APROVADA!{RESET}")
        print(f"  Ambos os Consumer Groups processaram a mensagem de forma independente.")
        print(f"  O padrão Publish-Subscribe (Fan-Out) está funcionando perfeitamente.")
    else:
        print(f"{RED}{BOLD}❌ VALIDAÇÃO FALHOU!{RESET}")
        print(f"  Um ou ambos os grupos não receberam a mensagem.")
    print(f"{BOLD}{'=' * 66}{RESET}\n")


if __name__ == "__main__":
    main()
