import json

import pika

from src.settings import settings

def publish_order_created(order_id: int) -> None:
    """Publish a simple 'order_created' event to RabbitMQ queue.

    This uses a short-lived BlockingConnection; acceptable for demo/dev.
    """
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_AMQP_PORT, credentials=credentials)

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    queue_name = settings.RABBITMQ_QUEUE
    # ensure queue exists
    channel.queue_declare(queue=queue_name, durable=True)

    body = json.dumps({"event": "order_created", "order_id": order_id})
    channel.basic_publish(exchange="", routing_key=queue_name, body=body)

    connection.close()
