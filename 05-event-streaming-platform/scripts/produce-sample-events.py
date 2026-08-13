#!/usr/bin/env python3
# =============================================================================
# scripts/produce-sample-events.py — Gerador de Eventos de Carga (Card 10)
# =============================================================================
# Publica N pedidos fictícios via HTTP na Producer API para:
#   - Popular as partições com volume real de mensagens
#   - Demonstrar distribuição automática por Message Key (order_id)
#   - Gerar lag nos Consumer Groups para observação
#
# Uso:
#   python3 scripts/produce-sample-events.py           # 10 pedidos (padrão)
#   python3 scripts/produce-sample-events.py --count 30  # 30 pedidos
#   python3 scripts/produce-sample-events.py --delay 0.5  # 0.5s entre pedidos
# =============================================================================

import argparse
import json
import random
import time
import urllib.error
import urllib.request
import uuid

API_URL = "http://localhost:8000/orders"

PRODUCTS = [
    ("prod-001", "Notebook Pro 15", 4999.90),
    ("prod-002", "Monitor 4K Ultrawide", 2799.00),
    ("prod-003", "Teclado Mecânico RGB", 459.90),
    ("prod-004", "Mouse Gamer 25K DPI", 349.00),
    ("prod-005", "Headset Surround 7.1", 599.90),
    ("prod-006", "SSD NVMe 2TB", 799.00),
    ("prod-007", "Placa de Vídeo RTX", 3999.00),
    ("prod-008", "Webcam 4K 60fps", 899.00),
    ("prod-009", "Cadeira Gamer Ergo", 2199.00),
    ("prod-010", "Hub USB-C 12 Portas", 299.90),
]

CUSTOMERS = [
    ("c-001", "ana@example.com"),
    ("c-002", "bruno@example.com"),
    ("c-003", "carlos@example.com"),
    ("c-004", "diana@example.com"),
    ("c-005", "edgar@example.com"),
]


def publish_order(customer_id: str, customer_email: str, items: list) -> dict | None:
    payload = {
        "customer_id": customer_id,
        "customer_email": customer_email,
        "items": items,
        "currency": "BRL",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  ❌ HTTP {e.code}: {e.read().decode()}")
        return None
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Gerador de eventos de carga para o Kafka.")
    parser.add_argument("--count", type=int, default=10, help="Número de pedidos a publicar (padrão: 10)")
    parser.add_argument("--delay", type=float, default=0.2, help="Intervalo entre pedidos em segundos (padrão: 0.2)")
    args = parser.parse_args()

    print("=" * 62)
    print(f"🚀 Publicando {args.count} pedidos fictícios...")
    print(f"   API: {API_URL} | Delay: {args.delay}s entre pedidos")
    print("=" * 62)
    print()

    ok = 0
    for i in range(1, args.count + 1):
        customer_id, customer_email = random.choice(CUSTOMERS)
        product_id, product_name, price = random.choice(PRODUCTS)
        qty = random.randint(1, 3)

        items = [{"product_id": product_id, "product_name": product_name,
                  "quantity": qty, "unit_price": str(price)}]

        result = publish_order(customer_id, customer_email, items)

        if result:
            ok += 1
            order_id = result.get("order_id", "???")
            published = "✅" if result.get("event_published") else "⚠️ sem Kafka"
            print(f"  [{i:>3}/{args.count}] {published} order_id={order_id[:8]}... | {customer_email} | {product_name} x{qty}")
        else:
            print(f"  [{i:>3}/{args.count}] ❌ Falha")

        if i < args.count:
            time.sleep(args.delay)

    print()
    print("=" * 62)
    print(f"✅ Concluído: {ok}/{args.count} pedidos publicados com sucesso.")
    print()
    print("💡 Para ver a distribuição nas partições, execute:")
    print("   ./scripts/describe-topics.sh")
    print("   ./scripts/watch-consumer-groups.sh")
    print("=" * 62)


if __name__ == "__main__":
    main()
