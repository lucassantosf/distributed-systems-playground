import json

import pika

from src.settings import settings
from src.infrastructure.logging import get_logger

logger = get_logger("src.infrastructure.messaging.publisher")


def publish_order_created(order_id: int, correlation_id: str | None = None) -> None:
    """Publish a simple 'order_created' event to a RabbitMQ exchange.

    This uses a short-lived BlockingConnection; acceptable for demo/dev.
    """
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_AMQP_PORT, credentials=credentials)

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    exchange_name = settings.RABBITMQ_EXCHANGE
    channel.exchange_declare(exchange=exchange_name, exchange_type=settings.RABBITMQ_EXCHANGE_TYPE, durable=True)

    payload = {"event": "order_created", "order_id": order_id, "correlation_id": correlation_id}
    body = json.dumps(payload)
    channel.basic_publish(exchange=exchange_name, routing_key="", body=body)
    logger.info(
        "Published order created event",
        extra={"event": "order_created", "order_id": order_id, "correlation_id": correlation_id, "exchange": exchange_name},
    )

    connection.close()
