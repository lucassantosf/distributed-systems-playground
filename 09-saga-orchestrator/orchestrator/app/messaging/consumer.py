"""
Consumer de replies do Saga Orchestrator.

Consome a fila 'saga.replies' em loop contínuo como uma asyncio.Task.
Despacha cada reply recebida para engine.handle_reply(...).
Faz ack somente após o processamento bem-sucedido.
Em caso de erro/exceção, faz nack(requeue=False) para encaminhamento à DLQ.
"""
import asyncio
import json
import logging
import os
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("saga-consumer")

try:
    from app.config import settings
    DEFAULT_QUEUE_REPLIES = settings.QUEUE_REPLIES
    DEFAULT_RABBITMQ_URL = settings.RABBITMQ_URL
except Exception:
    DEFAULT_QUEUE_REPLIES = os.getenv("QUEUE_REPLIES", "saga.replies")
    DEFAULT_RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

try:
    import aio_pika
    HAS_AIO_PIKA = True
except ImportError:
    HAS_AIO_PIKA = False
    aio_pika = None


class RepliesConsumer:
    """
    Consome respostas dos workers na fila saga.replies e entrega ao SagaEngine.
    """

    def __init__(
        self,
        channel: Any,
        engine: Any,
        queue_name: str = DEFAULT_QUEUE_REPLIES,
    ):
        self.channel = channel
        self.engine = engine
        self.queue_name = queue_name
        self.consumer_tag: Optional[str] = None
        self._is_running = False

    async def process_message(self, message: Any) -> None:
        """
        Processa uma mensagem recebida da fila saga.replies.

        Faz ack se processar com sucesso.
        Faz nack(requeue=False) em caso de erro para envio à DLQ.
        """
        body_str = ""
        try:
            body_bytes = message.body if isinstance(message.body, bytes) else message.body.encode("utf-8")
            body_str = body_bytes.decode("utf-8")
            reply_data = json.loads(body_str)

            command_id = reply_data.get("command_id")
            saga_id = reply_data.get("saga_id")
            command_type = reply_data.get("command_type")
            success = reply_data.get("success")

            logger.info(
                f"Processando reply recebida: {command_type} "
                f"[command_id={command_id}, saga_id={saga_id}, success={success}]"
            )

            # Executa a transição no engine
            await self.engine.handle_reply(reply_data)

            # Confirma o processamento com sucesso
            await message.ack()
            logger.info(f"ACK enviado com sucesso para command_id={command_id}")

        except Exception as exc:
            logger.error(
                f"Erro ao processar reply da Saga: {exc}. "
                f"Corpo recebido: {body_str}. "
                f"Enviando NACK(requeue=False) para direcionar à DLQ.",
                exc_info=True,
            )
            try:
                await message.nack(requeue=False)
            except Exception as nack_err:
                logger.error(f"Erro ao enviar NACK: {nack_err}", exc_info=True)

    async def run(self) -> None:
        """
        Inicia o consumo contínuo da fila saga.replies até ser cancelado.
        """
        self._is_running = True
        logger.info(f"Iniciando RepliesConsumer na fila '{self.queue_name}'...")

        try:
            # Garante que a fila está declarada
            if hasattr(self.channel, "declare_queue"):
                queue = await self.channel.declare_queue(self.queue_name, durable=True)
            else:
                queue = self.channel

            # Se a fila suportar iterator assíncrono (aio-pika padrão)
            if hasattr(queue, "iterator"):
                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        if not self._is_running:
                            break
                        await self.process_message(message)
            elif hasattr(queue, "consume"):
                self.consumer_tag = await queue.consume(self.process_message)
                while self._is_running:
                    await asyncio.sleep(0.5)
            else:
                while self._is_running:
                    await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info(f"RepliesConsumer da fila '{self.queue_name}' cancelado.")
            self._is_running = False
            raise
        except Exception as exc:
            logger.error(f"Erro inesperado no RepliesConsumer: {exc}", exc_info=True)
            self._is_running = False
            raise
        finally:
            self._is_running = False
            if self.consumer_tag and hasattr(self.channel, "basic_cancel"):
                try:
                    await self.channel.basic_cancel(self.consumer_tag)
                except Exception:
                    pass


def start_replies_consumer(
    channel: Any,
    engine: Any,
    queue_name: str = DEFAULT_QUEUE_REPLIES,
) -> asyncio.Task:
    """
    Cria e inicia o consumer de replies como uma asyncio.Task em background.
    """
    consumer = RepliesConsumer(channel=channel, engine=engine, queue_name=queue_name)
    task = asyncio.create_task(consumer.run(), name="saga-replies-consumer")
    return task


async def stop_replies_consumer(task: Optional[asyncio.Task]) -> None:
    """
    Cancela e aguarda o encerramento seguro do consumer.
    """
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

