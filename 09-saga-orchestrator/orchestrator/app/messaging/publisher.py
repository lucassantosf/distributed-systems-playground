"""
Publicador de comandos do Saga Orchestrator.

Responsável por serializar e despachar comandos para os workers
através do exchange direto 'saga.commands' com routing key igual ao serviço.
"""
import json
import logging
import os
import uuid
from typing import Any, Dict, Optional, Union

logger = logging.getLogger("saga-publisher")

try:
    from app.config import settings
    DEFAULT_EXCHANGE = settings.EXCHANGE_COMMANDS
    DEFAULT_RABBITMQ_URL = settings.RABBITMQ_URL
except Exception:
    DEFAULT_EXCHANGE = os.getenv("EXCHANGE_COMMANDS", "saga.commands")
    DEFAULT_RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

try:
    import aio_pika
    from aio_pika import DeliveryMode, ExchangeType
    HAS_AIO_PIKA = True
except ImportError:
    HAS_AIO_PIKA = False
    aio_pika = None

    class DeliveryMode:
        NOT_PERSISTENT = 1
        PERSISTENT = 2

    class ExchangeType:
        DIRECT = "direct"
        FANOUT = "fanout"
        TOPIC = "topic"


class CommandPublisher:
    """
    Publicador de comandos para os serviços mockados da Saga.
    """

    def __init__(
        self,
        channel: Optional[Any] = None,
        exchange_name: str = DEFAULT_EXCHANGE,
        rabbitmq_url: str = DEFAULT_RABBITMQ_URL,
    ):
        self.channel = channel
        self.exchange_name = exchange_name
        self.rabbitmq_url = rabbitmq_url
        self._connection = None
        self._exchange = None

    async def get_channel(self) -> Any:
        if self.channel is not None and not getattr(self.channel, "is_closed", False):
            return self.channel

        if not HAS_AIO_PIKA:
            raise RuntimeError("aio-pika não está instalado no ambiente")

        if self._connection is None or getattr(self._connection, "is_closed", False):
            logger.info(f"Conectando CommandPublisher ao RabbitMQ em {self.rabbitmq_url}...")
            self._connection = await aio_pika.connect_robust(self.rabbitmq_url)

        self.channel = await self._connection.channel()
        return self.channel

    async def get_exchange(self) -> Any:
        if self._exchange is not None:
            return self._exchange

        channel = await self.get_channel()
        if hasattr(channel, "get_exchange"):
            try:
                self._exchange = await channel.get_exchange(self.exchange_name, ensure=False)
            except Exception:
                self._exchange = await channel.declare_exchange(
                    self.exchange_name,
                    type=ExchangeType.DIRECT,
                    durable=True,
                )
        elif hasattr(channel, "declare_exchange"):
            self._exchange = await channel.declare_exchange(
                self.exchange_name,
                type=ExchangeType.DIRECT,
                durable=True,
            )
        else:
            self._exchange = channel

        return self._exchange

    def serialize_command(
        self,
        service: str,
        command_type: str,
        saga_id: Union[str, uuid.UUID],
        command_id: Union[str, uuid.UUID],
        attempt: int = 1,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Formata o dicionário do comando conforme o contrato com os workers.
        """
        return {
            "command_id": str(command_id),
            "command_type": command_type,
            "saga_id": str(saga_id),
            "attempt": int(attempt),
            "payload": payload if payload is not None else {},
        }

    async def publish_command(
        self,
        service: str,
        command_type: str,
        saga_id: Union[str, uuid.UUID],
        command_id: Union[str, uuid.UUID],
        attempt: int = 1,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Serializa e publica o comando no exchange saga.commands com routing key igual ao serviço.

        Args:
            service: nome do serviço destinatário (ex: 'inventory', 'payment', 'shipping', 'notification')
            command_type: identificador do comando (ex: 'ReservarEstoque', 'LiberarEstoque')
            saga_id: ID da Saga em execução
            command_id: UUID gerado para a tentativa (chave de idempotência)
            attempt: número da tentativa atual (iniciando em 1)
            payload: dados de negócio necessários para execução do comando

        Returns:
            Dict com a mensagem que foi publicada
        """
        command_data = self.serialize_command(
            service=service,
            command_type=command_type,
            saga_id=saga_id,
            command_id=command_id,
            attempt=attempt,
            payload=payload,
        )

        body_bytes = json.dumps(command_data, ensure_ascii=False).encode("utf-8")

        exchange = await self.get_exchange()

        if HAS_AIO_PIKA and aio_pika is not None:
            message = aio_pika.Message(
                body=body_bytes,
                content_type="application/json",
                correlation_id=str(command_id),
                delivery_mode=DeliveryMode.PERSISTENT,
                headers={
                    "saga_id": str(saga_id),
                    "command_type": command_type,
                    "attempt": int(attempt),
                    "service": service,
                },
            )
        else:
            class MockMessage:
                def __init__(self, body, content_type, correlation_id, delivery_mode, headers):
                    self.body = body
                    self.content_type = content_type
                    self.correlation_id = correlation_id
                    self.delivery_mode = delivery_mode
                    self.headers = headers

            message = MockMessage(
                body=body_bytes,
                content_type="application/json",
                correlation_id=str(command_id),
                delivery_mode=DeliveryMode.PERSISTENT,
                headers={
                    "saga_id": str(saga_id),
                    "command_type": command_type,
                    "attempt": int(attempt),
                    "service": service,
                },
            )

        # Publica no exchange com routing key igual ao nome do serviço
        if hasattr(exchange, "publish"):
            await exchange.publish(message, routing_key=service)
        elif hasattr(self.channel, "default_exchange") and hasattr(self.channel.default_exchange, "publish"):
            await self.channel.default_exchange.publish(message, routing_key=service)
        elif callable(exchange):
            res = exchange(message, routing_key=service)
            if hasattr(res, "__await__"):
                await res

        logger.info(
            f"Comando '{command_type}' publicado para serviço '{service}' "
            f"[command_id={command_id}, saga_id={saga_id}, attempt={attempt}]"
        )

        return command_data

    async def publish_to_dlq(
        self,
        saga_id: Union[str, uuid.UUID],
        payload: Dict[str, Any],
        reason: str = "COMPENSATION_FAILED",
    ) -> Dict[str, Any]:
        """
        Publica mensagem no exchange Dead Letter (saga.dlx) para a fila saga.dlq.
        Acionado quando as tentativas de compensação se esgotam (falha irrecuperável).
        """
        from datetime import datetime, timezone

        data = {
            "saga_id": str(saga_id),
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        body_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")

        channel = await self.get_channel()
        dlx_name = getattr(settings, "EXCHANGE_DLX", os.getenv("EXCHANGE_DLX", "saga.dlx"))

        if hasattr(channel, "declare_exchange"):
            dlx_exchange = await channel.declare_exchange(
                dlx_name,
                type=ExchangeType.FANOUT,
                durable=True,
            )
            if HAS_AIO_PIKA and aio_pika is not None:
                message = aio_pika.Message(
                    body=body_bytes,
                    content_type="application/json",
                    delivery_mode=DeliveryMode.PERSISTENT,
                    headers={
                        "saga_id": str(saga_id),
                        "reason": reason,
                    },
                )
            else:
                class MockMessage:
                    def __init__(self, body, content_type, delivery_mode, headers):
                        self.body = body
                        self.content_type = content_type
                        self.delivery_mode = delivery_mode
                        self.headers = headers

                message = MockMessage(
                    body=body_bytes,
                    content_type="application/json",
                    delivery_mode=DeliveryMode.PERSISTENT,
                    headers={
                        "saga_id": str(saga_id),
                        "reason": reason,
                    },
                )

            if hasattr(dlx_exchange, "publish"):
                await dlx_exchange.publish(message, routing_key="")
        elif hasattr(channel, "default_exchange") and hasattr(channel.default_exchange, "publish"):
            await channel.default_exchange.publish(
                aio_pika.Message(body=body_bytes, content_type="application/json"),
                routing_key="saga.dlq",
            )

        logger.warning(
            f"Mensagem de falha irrecuperável enviada para DLQ ({dlx_name}): "
            f"saga_id={saga_id}, reason={reason}"
        )
        return data

    async def close(self) -> None:
        """Encerra canal e conexão se gerenciados internamente."""
        if self.channel is not None and not getattr(self.channel, "is_closed", False):
            try:
                await self.channel.close()
            except Exception:
                pass
        if self._connection is not None and not getattr(self._connection, "is_closed", False):
            try:
                await self._connection.close()
            except Exception:
                pass
        self._exchange = None
        self.channel = None
        self._connection = None

