"""
Aplicação Principal — Notification Consumer (Cards 9, 22 e 23)
Consome eventos do tópico orders.created e orders.created-retry,
gerenciando notificações aos clientes, retry topics com backoff e DLT.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

# Adiciona diretório raiz do container ao PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.notification_service import process_order_created_notification
from shared.events.types import (
    EventType,
    TOPIC_ORDERS_CREATED_DLT,
    TOPIC_ORDERS_CREATED_RETRY,
)
from shared.kafka.consumer import KafkaConsumerWrapper
from shared.kafka.producer import KafkaProducerWrapper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("notification-consumer")

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
GROUP_ID = "notification-group"
MAIN_TOPIC = EventType.ORDER_CREATED.topic  # "orders.created"
RETRY_TOPIC = TOPIC_ORDERS_CREATED_RETRY    # "orders.created-retry"
DLT_TOPIC = TOPIC_ORDERS_CREATED_DLT        # "orders.created-dlt"

MAX_RETRIES = 3

# Producer para publicar em -retry e -dlt
producer = KafkaProducerWrapper(bootstrap_servers=BOOTSTRAP_SERVERS)


def handle_failure(event_data: dict, exc: Exception) -> None:
    """
    Roteia o evento que falhou para o Tópico de Retry ou DLT (Dead Letter Topic).

    Cards 22 (Retry) e 23 (DLT).
    """
    event_id = event_data.get("event_id")
    order_id = event_data.get("order_id")

    # Garante estrutura de retry_metadata no evento
    retry_meta = event_data.setdefault("retry_metadata", {
        "retry_count": 0,
        "max_retries": MAX_RETRIES,
        "original_topic": MAIN_TOPIC,
        "error_history": [],
    })

    current_retry = retry_meta.get("retry_count", 0) + 1
    retry_meta["retry_count"] = current_retry
    retry_meta["last_error"] = str(exc)
    retry_meta["error_history"].append({
        "attempt": current_retry,
        "error": str(exc),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    is_fatal = isinstance(exc, ValueError) or "fatal" in str(exc).lower()

    key_bytes = str(order_id or event_id).encode("utf-8")
    value_bytes = json.dumps(event_data).encode("utf-8")

    if not is_fatal and current_retry <= MAX_RETRIES:
        # Encaminha para o Tópico de Retry (Card 22)
        logger.warning(
            f"🔄 [RETRY PATTERN] Encaminhando evento {event_id} para '{RETRY_TOPIC}' "
            f"(Tentativa {current_retry}/{MAX_RETRIES}) | Erro: {exc}"
        )
        producer.produce(topic=RETRY_TOPIC, key=key_bytes, value=value_bytes)
        producer.flush()
    else:
        # Encaminha para o Dead Letter Topic (Card 23)
        reason = "Erro Fatal" if is_fatal else f"Esgotado limite de retentativas ({current_retry-1}/{MAX_RETRIES})"
        logger.error(
            f"☠️ [DLT PATTERN] Encaminhando evento {event_id} para '{DLT_TOPIC}' | Motivo: {reason} | Erro: {exc}"
        )
        producer.produce(topic=DLT_TOPIC, key=key_bytes, value=value_bytes)
        producer.flush()


def event_handler(event_data: dict) -> None:
    """Callback de processamento chamado para cada evento recebido do Kafka."""
    event_type = event_data.get("event_type")
    event_id = event_data.get("event_id")
    retry_meta = event_data.get("retry_metadata", {})
    current_retry = retry_meta.get("retry_count", 0)

    # Aplica Backoff Progressivo se for uma mensagem vindoura do Retry Topic
    if current_retry > 0:
        backoff_sec = min(1.5 * current_retry, 5.0)
        logger.info(
            f"⏳ [BACKOFF RETRY] Aplicando delay de {backoff_sec:.1f}s antes da tentativa {current_retry} "
            f"para o evento {event_id}..."
        )
        time.sleep(backoff_sec)

    logger.info(
        f"Evento recebido | type={event_type} event_id={event_id} "
        f"retry_count={current_retry}"
    )

    db = SessionLocal()
    try:
        if event_type == EventType.ORDER_CREATED.value:
            process_order_created_notification(db, event_data)
        else:
            logger.info(f"Tipo de evento ignorado por este consumidor: {event_type}")
    except Exception as exc:
        logger.error(f"Erro ao processar evento {event_id}: {exc}")
        db.rollback()
        # Dispara estratégia de resiliência (Retry / DLT)
        handle_failure(event_data, exc)
    finally:
        db.close()


def main():
    logger.info(f"Iniciando Notification Consumer com suporte a Retry & DLT...")
    topics_to_listen = [MAIN_TOPIC, RETRY_TOPIC]
    consumer = KafkaConsumerWrapper(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=GROUP_ID,
        topics=topics_to_listen,
        auto_offset_reset="earliest",
    )
    consumer.start_listening(handler=event_handler)


if __name__ == "__main__":
    main()
