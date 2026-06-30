#!/usr/bin/env python3
"""Notification worker that consumes 'order_created' events from RabbitMQ and simulates notification generation."""
import json
import time
from datetime import datetime
import os
import sys

# ensure project root (/app) is on sys.path so `import src` works when script
# is executed via a path (python workers/notification/worker.py)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pika

from src.settings import settings
from src.infrastructure.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("workers.notification.worker")

LOG_PATH = "/app/workers/notification/generated_notification.log"

def on_message(ch, method, properties, body):
    try:
        payload = json.loads(body)
        correlation_id = payload.get("correlation_id")
        if payload.get("event") == "order_created":
            order_id = payload.get("order_id")
            logger.info(
                "Processing order_created event",
                extra={"event": "order_created", "order_id": order_id, "worker": "notification", "queue": settings.RABBITMQ_NOTIFICATION_QUEUE, "correlation_id": correlation_id},
            )
            line = f"{datetime.utcnow().isoformat()} - Generating notification for order_id={order_id}\n"
            with open(LOG_PATH, "a") as f:
                f.write(line)
            logger.info(
                "Notification generated for order",
                extra={"event": "notification_generated", "order_id": order_id, "worker": "notification", "status": "generated", "correlation_id": correlation_id},
            )
            print(line.strip())
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        logger.exception(
            "Error processing notification message",
            extra={"event": "notification_processing_error", "worker": "notification", "error": str(exc), "correlation_id": correlation_id},
        )
        try:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception:
            pass

def main():
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_AMQP_PORT, credentials=credentials)

    while True:
        try:
            connection = pika.BlockingConnection(parameters)
            break
        except Exception as e:
            print("RabbitMQ not ready, retrying in 2s...", e)
            time.sleep(2)

    channel = connection.channel()
    exchange_name = settings.RABBITMQ_EXCHANGE
    queue_name = settings.RABBITMQ_NOTIFICATION_QUEUE
    dead_letter_exchange_name = settings.RABBITMQ_DEAD_LETTER_EXCHANGE
    dead_letter_queue_name = settings.RABBITMQ_NOTIFICATION_DLQ_QUEUE

    channel.exchange_declare(exchange=exchange_name, exchange_type=settings.RABBITMQ_EXCHANGE_TYPE, durable=True)
    channel.exchange_declare(exchange=dead_letter_exchange_name, exchange_type="direct", durable=True)
    channel.queue_declare(queue=dead_letter_queue_name, durable=True)
    channel.queue_bind(exchange=dead_letter_exchange_name, queue=dead_letter_queue_name, routing_key=dead_letter_queue_name)
    channel.queue_declare(queue=queue_name, durable=True, arguments={
        "x-dead-letter-exchange": dead_letter_exchange_name,
        "x-dead-letter-routing-key": dead_letter_queue_name,
    })
    channel.queue_bind(exchange=exchange_name, queue=queue_name)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=queue_name, on_message_callback=on_message)

    print("[notification_worker] Waiting for messages. To exit press CTRL+C")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        try:
            connection.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()