import asyncio
import json
import logging
import os
from typing import Tuple
import aio_pika

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("payment-worker")


def apply_business_rules(command_type: str, payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    total_amount = float(payload.get("total_amount", 0.0))
    order_id = str(payload.get("order_id", ""))

    if command_type == "ProcessarPagamento":
        # Falha transitória simulada: order_id terminando em 77 falha nas 2 primeiras tentativas
        if order_id.endswith("77") and attempt < 3:
            return False, {}, f"Erro transitório no gateway de pagamento (tentativa {attempt}/3)"

        # Pagamento recusado quando total_amount > 9999.99
        if total_amount > 9999.99:
            return False, {}, "Pagamento recusado: valor excede limite de crédito"

        return True, {"transaction_id": f"tx_{order_id}_{attempt}", "status": "approved"}, None

    elif command_type == "EstornarPagamento":
        return True, {"refund_id": f"ref_{order_id}", "status": "refunded"}, None

    return True, {}, None


async def process_message(message: aio_pika.IncomingMessage, channel: aio_pika.Channel):
    async with message.process():
        try:
            body = json.loads(message.body.decode())
            command_id = body.get("command_id")
            saga_id = body.get("saga_id")
            command_type = body.get("command_type")
            payload = body.get("payload", {})
            attempt = int(body.get("attempt", 1))

            logger.info(f"Recebido '{command_type}' (id={command_id}, saga={saga_id}, attempt={attempt})")
            success, result_data, error_message = apply_business_rules(command_type, payload, attempt)

            reply = {
                "command_id": command_id,
                "saga_id": saga_id,
                "command_type": command_type,
                "service": "payment",
                "success": success,
                "payload": result_data,
                "error_message": error_message,
            }

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(reply).encode(),
                    correlation_id=command_id,
                    content_type="application/json",
                ),
                routing_key="saga.replies",
            )
            logger.info(f"Resposta publicada para '{command_type}': success={success}")
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}", exc_info=True)


async def main():
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
    logger.info(f"Iniciando Payment Worker conectando a {rabbitmq_url}...")

    connection = None
    while connection is None:
        try:
            connection = await aio_pika.connect_robust(rabbitmq_url)
        except Exception as e:
            logger.warning(f"Aguardando RabbitMQ ({e})... Tentando novamente em 3s")
            await asyncio.sleep(3)

    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        queue = await channel.declare_queue("payment.commands", durable=True)
        await channel.declare_queue("saga.replies", durable=True)

        logger.info("Worker pronto. Escutando na fila 'payment.commands'...")
        await queue.consume(lambda msg: process_message(msg, channel))

        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
