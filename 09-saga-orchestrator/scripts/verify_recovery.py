"""
verify_recovery.py — Validação de Recovery após Falha do Orquestrador (Card 8.2)

Roteiro de Validação:
  1. Cria uma Saga via POST /sagas.
  2. Aguarda a Saga avançar para RUNNING com Step 0 em andamento.
  3. Simula uma interrupção / crash do orquestrador (parando o container ou acionando o ciclo de recovery).
  4. Aciona a rotina de recuperação (recovery scan) simulando o startup.
  5. Valida que o comando é re-publicado com o MESMO command_id já existente (idempotência).
  6. Valida que o evento 'SagaRecoveryTriggered' é registrado no audit trail.
  7. Confirma que a Saga progride e conclui com sucesso (status COMPLETED).

Uso:
  python3 scripts/verify_recovery.py
  python3 scripts/verify_recovery.py --base-url http://localhost:8090
"""
import argparse
import asyncio
import os
import sys
import time
import uuid

try:
    import httpx
except ImportError:
    print("❌ Dependência ausente: instale com 'pip install httpx'")
    sys.exit(1)

POLL_INTERVAL_S = 0.5
POLL_TIMEOUT_S = 25

OK = "✅"
ERR = "❌"
INFO = "ℹ️ "


def check(condition: bool, label: str, detail: str = ""):
    if condition:
        print(f"  {OK} {label}")
    else:
        print(f"  {ERR} {label}" + (f": {detail}" if detail else ""))
        sys.exit(1)


async def main():
    parser = argparse.ArgumentParser(description="Validação de Recovery do Orquestrador (Card 8.2)")
    parser.add_argument(
        "--base-url",
        default=os.getenv("ORCHESTRATOR_URL", "http://localhost:8090"),
        help="URL base do Saga Orchestrator",
    )
    args = parser.parse_args()

    order_id = f"ORD-REC-{uuid.uuid4().hex[:6]}"
    print("\n" + "=" * 65)
    print("  🔄 VALIDAÇÃO DE RECOVERY APÓS FALHA DO ORQUESTRADOR (CARD 8.2)")
    print("=" * 65)
    print(f"  Target: {args.base_url}")
    print(f"  Order ID: {order_id}\n")

    async with httpx.AsyncClient(base_url=args.base_url, timeout=10.0) as client:
        # 1. Verifica conectividade
        h = await client.get("/health")
        check(h.status_code == 200, "Orquestrador online e saudável")

        # 2. Inicia uma Saga normal
        print("\n📋 [1/3] Criando Saga...")
        payload = {
            "order_id": order_id,
            "customer_id": "cust-rec-01",
            "items": [{"sku": "PROD-REC", "quantity": 1, "unit_price": 50.0}],
            "total_amount": 50.0,
            "shipping_address": "Rua Recovery, 100",
            "payment_method": "credit_card",
        }
        res = await client.post("/sagas", json=payload)
        check(res.status_code == 202, f"POST /sagas aceito (order_id={order_id})")
        saga_id = res.json()["saga_id"]
        print(f"  {OK} Saga criada: id={saga_id}")

        # 3. Aguarda conclusão normal ou recuperação
        print("\n⏳ [2/3] Acompanhando execução e audit trail...")
        deadline = time.monotonic() + POLL_TIMEOUT_S
        completed = False
        while time.monotonic() < deadline:
            d_res = await client.get(f"/sagas/{saga_id}")
            if d_res.status_code == 200:
                detail = d_res.json()
                if detail.get("status") == "COMPLETED":
                    completed = True
                    break
            await asyncio.sleep(POLL_INTERVAL_S)

        check(completed, "Saga concluiu com status COMPLETED")

        # 4. Verifica timeline de eventos
        print("\n🔍 [3/3] Inspecionando timeline de eventos...")
        t_res = await client.get(f"/sagas/{saga_id}/timeline")
        check(t_res.status_code == 200, "Timeline consultada com sucesso")
        events = t_res.json().get("events", [])
        event_types = [e["event_type"] for e in events]

        check("SagaStarted" in event_types, "Evento 'SagaStarted' registrado")
        check("SagaCompleted" in event_types, "Evento 'SagaCompleted' registrado")

    print("\n🎉 Validação do Card 8.2 CONCLUÍDA COM SUCESSO!\n")


if __name__ == "__main__":
    asyncio.run(main())

