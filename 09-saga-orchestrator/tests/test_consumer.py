"""
Testes unitários para RepliesConsumer (consumer.py) — Card 3.2.

Cobre:
  - Processamento de reply com sucesso -> chama engine.handle_reply e message.ack()
  - Exceção durante handle_reply -> captura erro e chama message.nack(requeue=False)
  - Mensagem malformada (JSON inválido) -> captura erro e chama message.nack(requeue=False)
  - Inicialização e cancelamento seguro da asyncio.Task do consumer
"""
import asyncio
import json
import os
import sys
import unittest

# Permite importar orchestrator sem instalação
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))

from app.messaging.consumer import (
    RepliesConsumer,
    start_replies_consumer,
    stop_replies_consumer,
)


class MockIncomingMessage:
    """Mock de mensagem recebida do RabbitMQ."""
    def __init__(self, body: bytes):
        self.body = body
        self.acked = False
        self.nacked = False
        self.nack_requeue = None

    async def ack(self):
        self.acked = True

    async def nack(self, requeue=False):
        self.nacked = True
        self.nack_requeue = requeue


class MockEngine:
    """Mock do SagaEngine."""
    def __init__(self, should_fail=False):
        self.handled_replies = []
        self.should_fail = should_fail

    async def handle_reply(self, reply_data):
        if self.should_fail:
            raise RuntimeError("Erro simulado no banco ao persistir reply")
        self.handled_replies.append(reply_data)


class MockQueue:
    """Mock de fila RabbitMQ."""
    def __init__(self, messages=None):
        self.messages = messages or []
        self.durable = True

    async def consume(self, callback):
        for msg in self.messages:
            await callback(msg)
        return "consumer-tag-123"


class MockChannel:
    """Mock de canal RabbitMQ."""
    def __init__(self, queue=None):
        self._queue = queue or MockQueue()

    async def declare_queue(self, name, durable=True):
        return self._queue

    async def basic_cancel(self, consumer_tag):
        pass


class TestRepliesConsumer(unittest.IsolatedAsyncioTestCase):

    async def test_process_message_sucesso_faz_ack(self):
        engine = MockEngine()
        consumer = RepliesConsumer(channel=MockChannel(), engine=engine)

        payload = {
            "command_id": "cmd-123",
            "saga_id": "saga-456",
            "command_type": "ReservarEstoque",
            "service": "inventory",
            "success": True,
            "payload": {"reserved": True},
        }
        msg = MockIncomingMessage(body=json.dumps(payload).encode("utf-8"))

        await consumer.process_message(msg)

        # Engine recebeu a reply
        self.assertEqual(len(engine.handled_replies), 1)
        self.assertEqual(engine.handled_replies[0]["command_id"], "cmd-123")

        # Mensagem recebeu ACK
        self.assertTrue(msg.acked)
        self.assertFalse(msg.nacked)

    async def test_process_message_excecao_no_engine_faz_nack_sem_requeue(self):
        engine = MockEngine(should_fail=True)
        consumer = RepliesConsumer(channel=MockChannel(), engine=engine)

        payload = {
            "command_id": "cmd-err",
            "saga_id": "saga-err",
            "command_type": "ProcessarPagamento",
            "service": "payment",
            "success": False,
        }
        msg = MockIncomingMessage(body=json.dumps(payload).encode("utf-8"))

        await consumer.process_message(msg)

        # Mensagem NÃO foi acked
        self.assertFalse(msg.acked)
        # Mensagem recebeu NACK com requeue=False (vai para a DLQ)
        self.assertTrue(msg.nacked)
        self.assertFalse(msg.nack_requeue)

    async def test_process_message_json_invalido_faz_nack_sem_requeue(self):
        engine = MockEngine()
        consumer = RepliesConsumer(channel=MockChannel(), engine=engine)

        # Payload corrompido / JSON quebrado
        msg = MockIncomingMessage(body=b"{invalid-json: none,")

        await consumer.process_message(msg)

        # Engine nem foi chamado
        self.assertEqual(len(engine.handled_replies), 0)
        # Mensagem foi nacked sem requeue
        self.assertFalse(msg.acked)
        self.assertTrue(msg.nacked)
        self.assertFalse(msg.nack_requeue)

    async def test_lifecycle_start_e_stop_consumer_task(self):
        engine = MockEngine()
        channel = MockChannel()

        task = start_replies_consumer(channel=channel, engine=engine)
        self.assertIsInstance(task, asyncio.Task)
        self.assertFalse(task.done())

        # Encerramento limpo
        await stop_replies_consumer(task)
        self.assertTrue(task.done())
        self.assertTrue(task.cancelled())


if __name__ == "__main__":
    unittest.main()

