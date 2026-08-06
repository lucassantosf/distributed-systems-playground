import json
import time

import pika
import redis

from config import settings
from projection import build_read_model
from shared.events.product import PRODUCT_DELETED

redis_client = redis.from_url(settings.redis_url)


def process_event(event: dict):
    if settings.projection_delay_seconds:
        time.sleep(settings.projection_delay_seconds)

    if event.get("event") == PRODUCT_DELETED:
        product_id = event["product_id"]
        removed = redis_client.hdel("products", str(product_id))
        print(f"ProductDeleted: produto {product_id} removido do Read Model (removidos={removed})")
    else:
        read_model = build_read_model(event)
        print(f"Read Model: {read_model.model_dump_json(ensure_ascii=False)}")
        redis_client.hset("products", read_model.id, read_model.model_dump_json())


def attempt_count(properties) -> int:
    headers = properties.headers or {}
    return headers.get("x-retry-count", 0) + 1


def requeue_with_retry(ch, method, properties, body, attempts) -> float:
    delay = settings.retry_base_delay_seconds * (2 ** (attempts - 1))
    headers = dict(properties.headers or {})
    headers["x-retry-count"] = attempts
    ch.basic_publish(
        exchange="products",
        routing_key="",
        body=body,
        properties=pika.BasicProperties(headers=headers, delivery_mode=2),
    )
    ch.basic_ack(method.delivery_tag)
    return delay


def callback(ch, method, properties, body):
    event = json.loads(body)
    attempts = attempt_count(properties)
    print(f"Evento recebido (tentativa {attempts}/{settings.max_retries}): {json.dumps(event, ensure_ascii=False)}")

    try:
        process_event(event)
        ch.basic_ack(method.delivery_tag)
        print(f"Mensagem {method.delivery_tag} processada e confirmada (acked)")
    except Exception as e:
        if attempts >= settings.max_retries:
            print(f"ERRO (tentativa {attempts} >= max {settings.max_retries}): {e} -> DESCARTE definitivo da mensagem {method.delivery_tag}")
            ch.basic_nack(method.delivery_tag, requeue=False)
        else:
            delay = requeue_with_retry(ch, method, properties, body, attempts)
            print(f"ERRO (tentativa {attempts}/{settings.max_retries}): {e} -> republicada com x-retry-count={attempts}, novo retry em {delay:.1f}s")
            time.sleep(delay)


def main():
    params = pika.ConnectionParameters(host=settings.broker_host)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.exchange_declare(exchange="products", exchange_type="fanout", durable=True)
    channel.exchange_declare(exchange=settings.dlq_exchange, exchange_type="fanout", durable=True)
    channel.queue_declare(
        queue="product_events",
        durable=True,
        arguments={
            "x-dead-letter-exchange": settings.dlq_exchange,
            "x-dead-letter-routing-key": settings.dlq_queue,
        },
    )
    channel.queue_declare(queue=settings.dlq_queue, durable=True)
    channel.queue_bind(exchange="products", queue="product_events")
    channel.queue_bind(exchange=settings.dlq_exchange, queue=settings.dlq_queue)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue="product_events", on_message_callback=callback)

    print("Projection Worker started, waiting for events...")
    channel.start_consuming()


if __name__ == "__main__":
    main()
