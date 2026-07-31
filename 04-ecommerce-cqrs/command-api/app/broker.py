import json

import pika

from config import settings

connection: pika.BlockingConnection | None = None
channel: pika.adapters.blocking_connection.BlockingChannel | None = None


def connect():
    global connection, channel
    params = pika.ConnectionParameters(host=settings.broker_host)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.exchange_declare(exchange="products", exchange_type="fanout", durable=True)
    channel.queue_declare(queue="product_events", durable=True)
    channel.queue_bind(exchange="products", queue="product_events")


def publish_event(event: dict):
    global channel
    if channel is None or channel.is_closed:
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
        connection.close()
