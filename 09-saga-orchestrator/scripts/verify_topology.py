import asyncio
import json
import uuid
import aio_pika
from aio_pika import ExchangeType

RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"

SERVICES = ["inventory", "payment", "shipping", "notification"]


async def verify_topology():
    print(f"🔌 Conectando ao RabbitMQ em {RABBITMQ_URL}...")
    connection = await aio_pika.connect_robust(RABBITMQ_URL)

    async with connection:
        channel = await connection.channel()

        # 1. Verificar Exchange saga.commands
        print("\n🔍 1. Verificando exchange direct 'saga.commands'...")
        commands_exchange = await channel.get_exchange("saga.commands")
        print(f"   ✅ Exchange '{commands_exchange.name}' encontrada!")

        # 2. Verificar Exchange saga.dlx e DLQ
        print("\n🔍 2. Verificando DLX e DLQ...")
        dlx_exchange = await channel.get_exchange("saga.dlx")
        dlq = await channel.get_queue("saga.dlq")
        print(f"   ✅ DLX '{dlx_exchange.name}' e DLQ '{dlq.name}' encontradas!")

        # 3. Verificar fila de replies
        print("\n🔍 3. Verificando fila 'saga.replies'...")
        replies_queue = await channel.get_queue("saga.replies")
        print(f"   ✅ Fila '{replies_queue.name}' encontrada!")

        # 4. Verificar roteamento via saga.commands para cada serviço
        print("\n🔍 4. Testando roteamento: saga.commands -> {service}.commands...")
        for service in SERVICES:
            queue_name = f"{service}.commands"
            queue = await channel.get_queue(queue_name)

            test_payload = {
                "test_id": str(uuid.uuid4()),
                "target_service": service,
                "type": "topology_ping",
            }

            # Publica no exchange com routing_key = service
            await commands_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(test_payload).encode(),
                    content_type="application/json",
                ),
                routing_key=service,
            )

            # Consome diretamente da fila do serviço para garantir que o binding entregou
            msg = await queue.get(timeout=2)
            async with msg.process():
                received = json.loads(msg.body.decode())
                assert received["test_id"] == test_payload["test_id"]
                print(f"   ✅ Mensagem para '{service}' roteada com sucesso para '{queue_name}'")

        # 5. Testar Dead Lettering (Rejeição com requeue=False deve ir para saga.dlq)
        print("\n🔍 5. Testando Dead Lettering para 'saga.dlq'...")
        dlq_initial_count = dlq.declaration_result.message_count

        dl_test_id = str(uuid.uuid4())
        await commands_exchange.publish(
            aio_pika.Message(
                body=json.dumps({"dl_test_id": dl_test_id}).encode(),
                content_type="application/json",
            ),
            routing_key="inventory",
        )

        inventory_queue = await channel.get_queue("inventory.commands")
        incoming_msg = await inventory_queue.get(timeout=2)
        # Rejeita a mensagem sem requeue (deve cair na DLQ)
        await incoming_msg.reject(requeue=False)

        # Espera mensagem chegar na DLQ
        dlq_msg = await dlq.get(timeout=2)
        async with dlq_msg.process():
            dlq_body = json.loads(dlq_msg.body.decode())
            assert dlq_body.get("dl_test_id") == dl_test_id
            print("   ✅ Mensagem rejeitada foi capturada com sucesso pela 'saga.dlq'!")

    print("\n🎉 Todas as validações da topologia RabbitMQ passaram com sucesso!")


if __name__ == "__main__":
    asyncio.run(verify_topology())

