import asyncio
import json
import uuid
import httpx

BASE_URL = "http://localhost:8090"


async def main():
    print(f"🚀 Iniciando validação dos endpoints da API em {BASE_URL}...")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Health check
        res = await client.get("/health")
        assert res.status_code == 200, f"Falha no health check: {res.text}"
        print("✅ 1. GET /health -> OK")

        # 2. Criar uma nova Saga (POST /sagas)
        order_id = f"ord-test-{uuid.uuid4().hex[:8]}"
        payload = {
            "order_id": order_id,
            "customer_id": "cust-uuid-1",
            "items": [
                {"sku": "PROD-A", "quantity": 2, "unit_price": 50.0},
                {"sku": "PROD-B", "quantity": 1, "unit_price": 100.0},
            ],
            "total_amount": 200.0,
            "shipping_address": "Rua Central, 500 - SP",
            "payment_method": "credit_card",
        }

        res = await client.post("/sagas", json=payload)
        assert res.status_code == 202, f"Erro ao criar saga: {res.status_code} {res.text}"
        created_data = res.json()
        saga_id = created_data["saga_id"]
        assert created_data["status"] == "STARTED"
        assert created_data["order_id"] == order_id
        print(f"✅ 2. POST /sagas -> 202 Accepted (saga_id: {saga_id})")

        # 3. Consultar a Saga criada (GET /sagas/{saga_id})
        res = await client.get(f"/sagas/{saga_id}")
        assert res.status_code == 200, f"Erro ao obter saga: {res.text}"
        detail = res.json()
        assert detail["saga_id"] == saga_id
        assert detail["order_id"] == order_id
        assert len(detail["steps"]) == 4
        print(f"✅ 3. GET /sagas/{saga_id} -> 200 OK (status: {detail['status']}, steps: {len(detail['steps'])})")

        # 4. Consultar a timeline (GET /sagas/{saga_id}/timeline)
        res = await client.get(f"/sagas/{saga_id}/timeline")
        assert res.status_code == 200, f"Erro ao obter timeline: {res.text}"
        timeline = res.json()
        assert timeline["total_events"] >= 1
        assert timeline["events"][0]["event_type"] == "SagaStarted"
        print(f"✅ 4. GET /sagas/{saga_id}/timeline -> 200 OK ({timeline['total_events']} eventos)")

        # 5. Listar Sagas com filtros (GET /sagas?status=STARTED)
        res = await client.get("/sagas", params={"status": "STARTED", "limit": 10})
        assert res.status_code == 200
        sagas_list = res.json()
        assert any(s["saga_id"] == saga_id for s in sagas_list)
        print(f"✅ 5. GET /sagas -> 200 OK (encontradas {len(sagas_list)} sagas)")

        # 6. Testar 404 para Saga inexistente
        fake_id = str(uuid.uuid4())
        res = await client.get(f"/sagas/{fake_id}")
        assert res.status_code == 404
        print("✅ 6. GET /sagas/{fake_id} -> 404 Not Found (validado)")

    print("\n🎉 Todos os endpoints do Card 1.5 foram validados com sucesso!")


if __name__ == "__main__":
    asyncio.run(main())

