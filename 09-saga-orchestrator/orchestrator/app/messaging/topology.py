import logging
import aio_pika
from aio_pika import ExchangeType

from app.config import settings

logger = logging.getLogger("rabbitmq-topology")


async def setup_rabbitmq_topology(channel: aio_pika.abc.AbstractChannel) -> None:
    """
    Declara a topologia RabbitMQ de forma idempotente:
    1. saga.dlx (fanout exchange) -> saga.dlq (durable queue)
    2. saga.commands (direct exchange)
    3. Filas de comando por serviço com DLX configurado:
       - {service}.commands (durable, x-dead-letter-exchange=saga.dlx)
       - Binding: saga.commands -> routing_key={service}
    4. saga.replies (durable queue) para onde os workers enviam respostas
    """
    logger.info("Configurando topologia RabbitMQ...")

    # 1. Dead Letter Exchange (DLX) e Dead Letter Queue (DLQ)
    dlx = await channel.declare_exchange(
        name=settings.EXCHANGE_DLX,
        type=ExchangeType.FANOUT,
        durable=True,
    )

    dlq = await channel.declare_queue(
        name=settings.QUEUE_DLQ,
        durable=True,
    )
    await dlq.bind(dlx)
    logger.info(f"DLX '{settings.EXCHANGE_DLX}' vinculado à DLQ '{settings.QUEUE_DLQ}'")

    # 2. Commands Exchange (direct)
    commands_exchange = await channel.declare_exchange(
        name=settings.EXCHANGE_COMMANDS,
        type=ExchangeType.DIRECT,
        durable=True,
    )
    logger.info(f"Exchange '{settings.EXCHANGE_COMMANDS}' (direct) declarada")

    # 3. Filas por serviço com Dead Letter Exchange configurado
    for service in settings.SERVICES:
        queue_name = f"{service}.commands"
        queue = await channel.declare_queue(
            name=queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": settings.EXCHANGE_DLX,
            },
        )
        # Roteia mensagens onde routing_key == service para a fila correspondente
        await queue.bind(commands_exchange, routing_key=service)
        logger.info(f"Fila '{queue_name}' vinculada a '{settings.EXCHANGE_COMMANDS}' [rk={service}] com DLX configurado")

    # 4. Fila de respostas do orquestrador
    await channel.declare_queue(
        name=settings.QUEUE_REPLIES,
        durable=True,
    )
    logger.info(f"Fila '{settings.QUEUE_REPLIES}' declarada")

    logger.info("Topologia RabbitMQ inicializada com sucesso!")

