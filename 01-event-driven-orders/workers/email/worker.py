#!/usr/bin/env python3
"""Simple email worker that consumes 'order_created' events from RabbitMQ
and writes a simulated 'Sending email...' line into a log file.
"""
import json
import time
from datetime import datetime
import os
import sys

# ensure project root (/app) is on sys.path so `import src` works when script
# is executed via a path (python workers/email/worker.py)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pika

from src.settings import settings
from src.infrastructure.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("workers.email.worker")

LOG_PATH = "/app/workers/email/sent_emails.log"


def get_retry_count(properties):
    headers = getattr(properties, "headers", None) or {}
    return int(headers.get("x-retries", 0))


def republish_to_retry(ch, body, headers, retry_queue):
    headers = (headers.copy() if headers else {})
    headers["x-retries"] = int(headers.get("x-retries", 0)) + 1
    ch.basic_publish(
        exchange="",
        routing_key=retry_queue,
        body=body,
        properties=pika.BasicProperties(delivery_mode=2, headers=headers, content_type="application/json"),
    )


def on_message(ch, method, properties, body):
    try:
        payload = json.loads(body)
        correlation_id = payload.get("correlation_id")
        if payload.get("event") == "order_created":
            order_id = payload.get("order_id")
            retry_count = get_retry_count(properties)
            logger.info(
                "Processing order_created event",
                extra={"event": "order_created", "order_id": order_id, "worker": "email", "queue": settings.RABBITMQ_EMAIL_QUEUE, "retry_count": retry_count, "correlation_id": correlation_id},
            )
            # simulate failure for order 99 to test retry behavior
            if retry_count < settings.RABBITMQ_MAX_RETRIES and order_id == 99:
                logger.warning(
                    "Simulating retryable email failure",
                    extra={"event": "order_created", "order_id": order_id, "worker": "email", "retry_count": retry_count, "status": "retrying", "correlation_id": correlation_id},
                )
                republish_to_retry(ch, body, getattr(properties, "headers", None), settings.RABBITMQ_EMAIL_RETRY_QUEUE)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            line = f"{datetime.utcnow().isoformat()} - Sending email for order_id={order_id}\n"
            with open(LOG_PATH, "a") as f:
                f.write(line)
            logger.info(
                "Email sent for order",
                extra={"event": "email_sent", "order_id": order_id, "worker": "email", "status": "sent", "correlation_id": correlation_id},
            )
            print(line.strip())
            # persist email log to database
            try:
                from src.infrastructure.database import SessionLocal
                from src.modules.email_logs.models import EmailLog

                db = SessionLocal()
                try:
                    entry = EmailLog(order_id=order_id, status="sent", message="Simulated send")
                    db.add(entry)
                    db.commit()
                finally:
                    db.close()
            except Exception:
                logger.exception(
                    "Failed to persist email log",
                    extra={"event": "email_log_failure", "order_id": order_id, "worker": "email", "correlation_id": correlation_id},
                )
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        logger.exception(
            "Error processing email message",
            extra={"event": "email_processing_error", "worker": "email", "error": str(exc), "correlation_id": correlation_id},
        )
        try:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception:
            pass

def main():
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_AMQP_PORT, credentials=credentials)

    # retry loop for broker availability
    while True:
        try:
            connection = pika.BlockingConnection(parameters)
            break
        except Exception as e:
            print("RabbitMQ not ready, retrying in 2s...", e)
            time.sleep(2)

    channel = connection.channel()
    exchange_name = settings.RABBITMQ_EXCHANGE
    queue_name = settings.RABBITMQ_EMAIL_QUEUE
    retry_queue_name = settings.RABBITMQ_EMAIL_RETRY_QUEUE
    dead_letter_exchange_name = settings.RABBITMQ_DEAD_LETTER_EXCHANGE
    dead_letter_queue_name = settings.RABBITMQ_EMAIL_DLQ_QUEUE

    channel.exchange_declare(exchange=exchange_name, exchange_type=settings.RABBITMQ_EXCHANGE_TYPE, durable=True)
    channel.exchange_declare(exchange=dead_letter_exchange_name, exchange_type="direct", durable=True)
    channel.queue_declare(queue=dead_letter_queue_name, durable=True)
    channel.queue_bind(exchange=dead_letter_exchange_name, queue=dead_letter_queue_name, routing_key=dead_letter_queue_name)
    channel.queue_declare(queue=queue_name, durable=True, arguments={
        "x-dead-letter-exchange": dead_letter_exchange_name,
        "x-dead-letter-routing-key": dead_letter_queue_name,
    })
    channel.queue_bind(exchange=exchange_name, queue=queue_name)
    channel.queue_declare(
        queue=retry_queue_name,
        durable=True,
        arguments={
            "x-message-ttl": settings.RABBITMQ_RETRY_DELAY_MS,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": queue_name,
        },
    )
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=queue_name, on_message_callback=on_message)

    print("[email_worker] Waiting for messages. To exit press CTRL+C")
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
