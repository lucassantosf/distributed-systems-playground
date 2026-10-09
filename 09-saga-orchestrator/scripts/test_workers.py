import asyncio
import json
import uuid
import aio_pika

RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"

TEST_CASES = [
    {
        "service": "inventory",
        "queue": "inventory.commands",
        "command_type": "ReservarEstoque",
        "payload": {
            "order_id": "test-order-1",
            "items": [{"sku": "PROD-001", "quantity": 1}],
            "total_amount": 100.0,
        },
    },
    {
        "service": "payment",
        "queue": "payment.commands",
        "command_type": "ProcessarPagamento",
        "payload": {
            "order_id": "test-order-1",
            "total_amount": 150.0,
        },
    },
    {
        "service": "shipping",
        "queue": "shipping.commands",
        "command_type": "DespacharPedido",
        "payload": {
            "order_id": "test-order-1",
            "shipping_address": "Rua Teste, 123",
        },
    },
    {
        "service": "notification",
        "queue": "notification.commands",
        "command_type": "NotificarCliente",
        "payload": {
            "customer_id": "cust-999",
            "message": "Pedido aprovado",
        },
    },
]


async def run_validation():
    print(f"🔌 Conectando ao RabbitMQ ({RABBITMQ_URL})...")
    connection = await aio_pika.connect_robust(RABBITMQ_URL)

    async with connection:
        channel = await connection.channel()
        replies_queue = await channel.declare_queue("saga.replies", durable=True)

        for test in TEST_CASES:
            command_id = str(uuid.uuid4())
            saga_id = str(uuid.uuid4())
            service_name = test["service"]
            queue_name = test["queue"]
            command_type = test["command_type"]

            command_message = {
                "command_id": command_id,
                "saga_id": saga_id,
                "command_type": command_type,
                "payload": test["payload"],
                "attempt": 1,
            }

            print(f"\n📤 Enviando '{command_type}' para '{queue_name}'...")
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(command_message).encode(),
                    correlation_id=command_id,
                    content_type="application/json",
                ),
                routing_key=queue_name,
            )

            print(f"⏳ Aguardando reply em 'saga.replies'...")
            answered = False
            for _ in range(50):
                await asyncio.sleep(0.1)
                try:
                    incoming_msg = await replies_queue.get(no_ack=False)
                    async with incoming_msg.process():
                        reply_data = json.loads(incoming_msg.body.decode())
                        if reply_data.get("command_id") == command_id:
                            status_str = "SUCESSO ✅" if reply_data.get("success") else "FALHA ❌"
                            print(f"   [{service_name}] -> {status_str} (cmd={reply_data.get('command_type')})")
                            print(f"   Payload: {reply_data.get('payload')}")
                            answered = True
                            break
                except aio_pika.exceptions.QueueEmpty:
                    pass

            if not answered:
                print(f"❌ Timeout aguardando resposta de [{service_name}]")

    print("\n🏁 Validação dos workers finalizada!")


if __name__ == "__main__":
    asyncio.run(run_validation())

