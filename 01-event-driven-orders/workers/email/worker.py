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
        if payload.get("event") == "order_created":
            order_id = payload.get("order_id")
            retry_count = get_retry_count(properties)
            # simulate failure for order 99 to test retry behavior
            if retry_count < settings.RABBITMQ_MAX_RETRIES and order_id == 99:
                print(f"Simulating failure for order_id={order_id}, retry_count={retry_count}")
                republish_to_retry(ch, body, getattr(properties, "headers", None), settings.RABBITMQ_EMAIL_RETRY_QUEUE)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            line = f"{datetime.utcnow().isoformat()} - Sending email for order_id={order_id}\n"
            with open(LOG_PATH, "a") as f:
                f.write(line)
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
            except Exception as db_exc:
                print("Failed to persist email log:", db_exc)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        print("Error processing message:", exc)
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
    channel.exchange_declare(exchange=exchange_name, exchange_type=settings.RABBITMQ_EXCHANGE_TYPE, durable=True)
    channel.queue_declare(queue=queue_name, durable=True)
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
