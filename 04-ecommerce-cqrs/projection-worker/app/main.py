import json

import pika
import redis

from config import settings
from projection import build_read_model

redis_client = redis.from_url(settings.redis_url)


def callback(ch, method, properties, body):
    event = json.loads(body)
    print(f"Evento recebido: {json.dumps(event, ensure_ascii=False)}")

    read_model = build_read_model(event)
    print(f"Read Model: {json.dumps(read_model, ensure_ascii=False)}")

    redis_client.hset("products", read_model["id"], json.dumps(read_model))

    ch.basic_ack(method.delivery_tag)


def main():
    params = pika.ConnectionParameters(host=settings.broker_host)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.exchange_declare(exchange="products", exchange_type="fanout", durable=True)
    channel.queue_declare(queue="product_events", durable=True)
    channel.queue_bind(exchange="products", queue="product_events")

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue="product_events", on_message_callback=callback)

    print("Projection Worker started, waiting for events...")
    channel.start_consuming()


if __name__ == "__main__":
    main()
