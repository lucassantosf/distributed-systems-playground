import asyncio
import json
import logging
import os

try:
    import aio_pika
except ImportError:
    class _DummyMessage:
        def __init__(self, body, correlation_id=None, content_type=None, headers=None, delivery_mode=None):
            self.body = body
            self.correlation_id = correlation_id
            self.content_type = content_type
            self.headers = headers
            self.delivery_mode = delivery_mode

    class _DummyAioPika:
        Message = _DummyMessage
        IncomingMessage = Any if "Any" in globals() else object
        Channel = Any if "Any" in globals() else object

    aio_pika = _DummyAioPika

try:
    from . import idempotency_store
    from .rules import apply_business_rules
except ImportError:
    import idempotency_store
    from rules import apply_business_rules

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("payment-worker")


async def process_message(message: aio_pika.IncomingMessage, channel: aio_pika.Channel):
    async with message.process():
        try:
            body = json.loads(message.body.decode())
            command_id = body.get("command_id")
            saga_id = body.get("saga_id")
            command_type = body.get("command_type")
            payload = body.get("payload", {})
            attempt = int(body.get("attempt", 1))

            is_comp = command_type == "EstornarPagamento"
            prefix = "[COMPENSAÇÃO]" if is_comp else "[EXECUÇÃO]"
            logger.info(f"{prefix} Recebido '{command_type}' (id={command_id}, saga={saga_id}, attempt={attempt})")

            # Card 6.2 — Idempotência: retorna resultado cacheado sem re-executar
            reply = idempotency_store.get(command_id)
            if reply is None:
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
                idempotency_store.save(command_id, reply)

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(reply).encode(),
                    correlation_id=command_id,
                    content_type="application/json",
                ),
                routing_key="saga.replies",
            )
            logger.info(f"{prefix} Resposta publicada para '{command_type}': success={reply.get('success')}")
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

        dlx_exchange = os.getenv("EXCHANGE_DLX", "saga.dlx")
        queue = await channel.declare_queue(
            "payment.commands",
            durable=True,
            arguments={"x-dead-letter-exchange": dlx_exchange},
        )
        await channel.declare_queue("saga.replies", durable=True)

        logger.info("Worker pronto. Escutando na fila 'payment.commands'...")
        await queue.consume(lambda msg: process_message(msg, channel))

        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
