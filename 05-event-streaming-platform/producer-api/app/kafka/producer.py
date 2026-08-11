"""
Producer Kafka do producer-api.
Define tópicos e instancia o KafkaProducerWrapper com configuração do ambiente.
"""

import os

from shared.kafka.producer import KafkaProducerWrapper

# ── Tópicos ────────────────────────────────────────────────────────────────
# Nomes definitivos a serem organizados por domínio no Card 7.
TOPIC_ORDERS_CREATED = "orders.created"
TOPIC_ORDERS_UPDATED = "orders.updated"

# ── Instância singleton ────────────────────────────────────────────────────
_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

_producer_instance: KafkaProducerWrapper | None = None


def get_kafka_producer() -> KafkaProducerWrapper:
    """
    Retorna a instância singleton do KafkaProducerWrapper.
    FastAPI dependency — reutiliza o mesmo Producer durante o ciclo de vida da app.
    """
    global _producer_instance
    if _producer_instance is None:
        _producer_instance = KafkaProducerWrapper(bootstrap_servers=_BOOTSTRAP_SERVERS)
    return _producer_instance
