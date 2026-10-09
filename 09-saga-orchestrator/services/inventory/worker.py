import asyncio
import json
import logging
import os
from typing import Tuple
import aio_pika

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("inventory-worker")


def apply_business_rules(command_type: str, payload: dict, attempt: int = 1) -> Tuple[bool, dict, str | None]:
    items = payload.get("items", [])
    order_id = str(payload.get("order_id", ""))

    if command_type == "ReservarEstoque":
        for item in items:
            if "ESGOTADO" in str(item.get("sku", "")):
                return False, {}, "Estoque indisponível: produto esgotado"
        return True, {"reserved_items": len(items)}, None

    elif command_type == "LiberarEstoque":
        if order_id.endswith("66"):
            return False, {}, "Falha fatal na compensação do estoque"
        return True, {"status": "stock_released"}, None

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
                "service": "inventory",
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
    logger.info(f"Iniciando Inventory Worker conectando a {rabbitmq_url}...")

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

        queue = await channel.declare_queue("inventory.commands", durable=True)
        await channel.declare_queue("saga.replies", durable=True)

        logger.info("Worker pronto. Escutando na fila 'inventory.commands'...")
        await queue.consume(lambda msg: process_message(msg, channel))

        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
