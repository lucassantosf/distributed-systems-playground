import json
import threading

import pika
from pika.exceptions import AMQPError

from config import settings

connection: pika.BlockingConnection | None = None
channel: pika.adapters.blocking_connection.BlockingChannel | None = None
_publish_lock = threading.Lock()


def connect():
    global connection, channel
    params = pika.ConnectionParameters(host=settings.broker_host)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.exchange_declare(exchange="products", exchange_type="fanout", durable=True)
    channel.queue_declare(
        queue="product_events",
        durable=True,
        arguments={
            "x-dead-letter-exchange": settings.dlq_exchange,
            "x-dead-letter-routing-key": settings.dlq_queue,
        },
    )
    channel.queue_bind(exchange="products", queue="product_events")


def _ensure_connected():
    global connection, channel
    if channel is None or channel.is_closed:
        connect()
    elif connection and connection.is_closed:
        connect()


def publish_event(event: dict):
    with _publish_lock:
        try:
            _ensure_connected()
            channel.basic_publish(
                exchange="products",
                routing_key="",
                body=json.dumps(event).encode(),
                properties=pika.BasicProperties(delivery_mode=2),
            )
        except AMQPError:
            connect()
            channel.basic_publish(
                exchange="products",
                routing_key="",
                body=json.dumps(event).encode(),
                properties=pika.BasicProperties(delivery_mode=2),
            )


def close():
    global connection
    if connection and not connection.is_closed:
        try:
            connection.close()
        except AMQPError:
            pass
