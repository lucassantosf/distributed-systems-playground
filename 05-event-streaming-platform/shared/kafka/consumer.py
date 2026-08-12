"""
Wrapper base do Kafka Consumer (confluent-kafka).
Reutilizável por qualquer consumidor da plataforma.
"""

import json
import logging
import signal
import sys
from typing import Callable

from confluent_kafka import Consumer, KafkaError, KafkaException

logger = logging.getLogger(__name__)


class KafkaConsumerWrapper:
    """
    Wrapper reutilizável sobre o Consumer do confluent-kafka.
    Encapsula subscrição, loop de poll, desserialização JSON e graceful shutdown.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        topics: list[str],
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = True,
    ) -> None:
        self.topics = topics
        self.running = True

        config = {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": auto_offset_reset,
            "enable.auto.commit": enable_auto_commit,
        }

        self._consumer = Consumer(config)
        self._consumer.subscribe(topics)
        logger.info(
            f"KafkaConsumer conectado em: {bootstrap_servers} | "
            f"group_id={group_id} | topics={topics}"
        )

        # Captura sinais de interrupção (Ctrl+C / Docker stop) para encerramento gracioso
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def start_listening(self, handler: Callable[[dict], None]) -> None:
        """
        Inicia o loop continuo de consumo.

        Para cada mensagem recebida, desserializa o payload de JSON bytes
        para dict e invoca a função `handler(event_dict)`.

        Args:
            handler: Função que recebe o evento em dict e realiza o processamento.
        """
        logger.info(f"Iniciando escuta de eventos nos tópicos: {self.topics}...")
        try:
            while self.running:
                msg = self._consumer.poll(timeout=1.0)
                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Erro no Kafka Consumer: {msg.error()}")
                        raise KafkaException(msg.error())

                try:
                    # Desserializa payload de bytes JSON para dicionário Python
                    value_str = msg.value().decode("utf-8")
                    event_data = json.loads(value_str)

                    # Executa o processador do consumidor
                    handler(event_data)

                    if not self._consumer.assignment():
                        continue

                except json.JSONDecodeError as err:
                    logger.error(f"Erro ao desserializar JSON da mensagem: {err}")
                except Exception as err:
                    logger.error(f"Erro no processamento da mensagem: {err}", exc_info=True)

        finally:
            self.close()

    def _signal_handler(self, sig, frame) -> None:
        logger.info("Sinal de interrupção recebido. Encerrando consumidor graciosamente...")
        self.running = False

    def close(self) -> None:
        """Fecha o consumidor e envia commit final dos offsets ao broker."""
        logger.info("Fechando conexão do Kafka Consumer...")
        self._consumer.close()
        logger.info("Kafka Consumer encerrado com sucesso.")
