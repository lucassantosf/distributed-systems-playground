"""
Wrapper base do Kafka Producer (confluent-kafka).
Reutilizável por qualquer serviço da plataforma.
"""

import logging

from confluent_kafka import Producer

logger = logging.getLogger(__name__)


class KafkaProducerWrapper:
    """
    Wrapper fino sobre o Producer do confluent-kafka.
    Encapsula configuração, produção e callback de entrega.
    """

    def __init__(self, bootstrap_servers: str) -> None:
        self._producer = Producer({"bootstrap.servers": bootstrap_servers})
        logger.info(f"KafkaProducer conectado em: {bootstrap_servers}")

    def produce(self, topic: str, key: bytes, value: bytes) -> None:
        """
        Publica uma mensagem no tópico especificado.

        Args:
            topic: Nome do tópico Kafka.
            key:   Message Key em bytes (ex.: order_id) — garante ordering por partição.
            value: Payload do evento serializado em JSON bytes.
        """
        self._producer.produce(
            topic=topic,
            key=key,
            value=value,
            on_delivery=self._delivery_report,
        )
        # poll(0) processa callbacks pendentes sem bloquear
        self._producer.poll(0)

    def produce_event(self, event) -> None:
        """
        Publica um evento derivado do BaseEvent com roteamento automático (Card 8).

        Determina o tópico de destino baseado em `event.event_type.topic`,
        extrai a Message Key (`event.to_kafka_key()`) e o payload (`event.to_kafka_value()`).

        Args:
            event: Instância de evento (ex.: OrderCreatedEvent, OrderUpdatedEvent).
        """
        topic = event.event_type.topic
        self.produce(
            topic=topic,
            key=event.to_kafka_key(),
            value=event.to_kafka_value(),
        )


    def flush(self, timeout: float = 10.0) -> None:
        """Aguarda a entrega de todas as mensagens pendentes."""
        self._producer.flush(timeout)

    @staticmethod
    def _delivery_report(err, msg) -> None:
        """Callback invocado pelo confluent-kafka após tentativa de entrega."""
        if err:
            logger.error(f"Falha na entrega | topic={msg.topic()} erro={err}")
        else:
            logger.info(
                f"Evento entregue | topic={msg.topic()} "
                f"partition={msg.partition()} offset={msg.offset()}"
            )
