"""
Aplicação Principal — Inventory Consumer (Cards 13 e 25)
Consome eventos do tópico orders.created, reserva estoque
e publica o evento derivado InventoryReserved no tópico inventory.reserved.

Padrão implementado no Card 25: Consumidor-que-também-é-Produtor.
Um consumidor de eventos pode — e deve — publicar novos eventos derivados
quando completa uma ação relevante para o domínio, sem acoplamento com
os produtores originais ou com outros consumidores.
"""

import logging
import os
import sys

# Adiciona diretório raiz do container ao PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.inventory_service import process_order_created_inventory
from shared.events.types import EventType
from shared.kafka.consumer import KafkaConsumerWrapper
from shared.kafka.producer import KafkaProducerWrapper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("inventory-consumer")

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
GROUP_ID = "inventory-group"
TOPIC = EventType.ORDER_CREATED.topic  # "orders.created"

# Producer para publicar InventoryReserved no tópico inventory.reserved (Card 25)
producer = KafkaProducerWrapper(bootstrap_servers=BOOTSTRAP_SERVERS)


def event_handler(event_data: dict) -> None:
    """Callback de processamento chamado para cada evento recebido do Kafka."""
    event_type = event_data.get("event_type")
    logger.info(f"Evento recebido no InventoryConsumer | type={event_type} event_id={event_data.get('event_id')}")

    db = SessionLocal()
    try:
        if event_type == EventType.ORDER_CREATED.value:
            process_order_created_inventory(db, event_data, producer)
        else:
            logger.info(f"Tipo de evento ignorado por este consumidor: {event_type}")
    except Exception as exc:
        logger.error(f"Erro ao processar evento de estoque: {exc}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def main():
    logger.info("Iniciando Inventory Consumer (com publicação de InventoryReserved — Card 25)...")
    consumer = KafkaConsumerWrapper(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=GROUP_ID,
        topics=[TOPIC],
        auto_offset_reset="earliest",
    )
    consumer.start_listening(handler=event_handler)


if __name__ == "__main__":
    main()
