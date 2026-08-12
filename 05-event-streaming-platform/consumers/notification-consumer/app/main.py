"""
Aplicação Principal — Notification Consumer (Card 9)
Consome eventos do tópico orders.created e envia notificações aos clientes.
"""

import logging
import os
import sys

# Adiciona diretório raiz do container ao PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.notification_service import process_order_created_notification
from shared.events.types import EventType
from shared.kafka.consumer import KafkaConsumerWrapper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("notification-consumer")

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
GROUP_ID = "notification-group"
TOPIC = EventType.ORDER_CREATED.topic  # "orders.created"


def event_handler(event_data: dict) -> None:
    """Callback de processamento chamado para cada evento recebido do Kafka."""
    event_type = event_data.get("event_type")
    logger.info(f"Evento recebido | type={event_type} event_id={event_data.get('event_id')}")

    db = SessionLocal()
    try:
        if event_type == EventType.ORDER_CREATED.value:
            process_order_created_notification(db, event_data)
        else:
            logger.info(f"Tipo de evento ignorado por este consumidor: {event_type}")
    except Exception as exc:
        logger.error(f"Erro ao processar evento: {exc}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def main():
    logger.info("Iniciando Notification Consumer...")
    consumer = KafkaConsumerWrapper(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=GROUP_ID,
        topics=[TOPIC],
        auto_offset_reset="earliest",
    )
    consumer.start_listening(handler=event_handler)


if __name__ == "__main__":
    main()
