import json

import pika

from src.settings import settings

def publish_order_created(order_id: int) -> None:
    """Publish a simple 'order_created' event to a RabbitMQ exchange.

    This uses a short-lived BlockingConnection; acceptable for demo/dev.
    """
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_AMQP_PORT, credentials=credentials)

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    exchange_name = settings.RABBITMQ_EXCHANGE
    channel.exchange_declare(exchange=exchange_name, exchange_type=settings.RABBITMQ_EXCHANGE_TYPE, durable=True)

    body = json.dumps({"event": "order_created", "order_id": order_id})
    channel.basic_publish(exchange=exchange_name, routing_key="", body=body)

    connection.close()
