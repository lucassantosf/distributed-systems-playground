"""
Testes unitários para CommandPublisher (publisher.py) — Card 3.1.

Cobre:
  - Formatação e serialização do payload de comando
  - Publicação no exchange correto com routing key igual ao serviço
  - Metadados da mensagem: content_type, correlation_id, delivery_mode e headers
  - Conversão de UUIDs para string
  - Integração com SagaEngine
"""
import asyncio
import json
import os
import sys
import unittest
import uuid

# Permite importar orchestrator sem instalação
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))

from app.core.enums import SagaStatus, StepStatus
from app.core.engine import SagaEngine
from app.core.workflow import ORDER_WORKFLOW
from app.messaging.publisher import CommandPublisher
from app.models.saga import Saga


class MockExchange:
    """Mock do aio_pika.Exchange para gravar publicações."""
    def __init__(self, name="saga.commands"):
        self.name = name
        self.published_messages = []

    async def publish(self, message, routing_key):
        self.published_messages.append({
            "message": message,
            "routing_key": routing_key,
        })


class MockChannel:
    """Mock de channel do RabbitMQ."""
    def __init__(self, exchange=None):
        self._exchange = exchange or MockExchange()
        self.is_closed = False

    async def get_exchange(self, name, ensure=False):
        return self._exchange

    async def declare_exchange(self, name, type="direct", durable=True):
        return self._exchange


class MockSession:
    """Sessão em memória para o engine."""
    def __init__(self):
        self.sagas = {}
        self.sagas_by_order = {}

    def add(self, obj):
        if isinstance(obj, Saga):
            self.sagas[str(obj.id)] = obj
            self.sagas_by_order[obj.order_id] = obj

    async def get_saga(self, saga_id: str):
        return self.sagas.get(str(saga_id))

    async def get_saga_by_order_id(self, order_id: str):
        return self.sagas_by_order.get(order_id)


class TestCommandPublisher(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.exchange = MockExchange(name="saga.commands")
        self.channel = MockChannel(exchange=self.exchange)
        self.publisher = CommandPublisher(
            channel=self.channel,
            exchange_name="saga.commands",
        )

    def test_serialize_command_formato_e_tipos(self):
        saga_id = uuid.uuid4()
        command_id = uuid.uuid4()
        payload = {"order_id": "ORD-100", "total": 99.9}

        serialized = self.publisher.serialize_command(
            service="inventory",
            command_type="ReservarEstoque",
            saga_id=saga_id,
            command_id=command_id,
            attempt=2,
            payload=payload,
        )

        self.assertEqual(serialized["command_id"], str(command_id))
        self.assertEqual(serialized["saga_id"], str(saga_id))
        self.assertEqual(serialized["command_type"], "ReservarEstoque")
        self.assertEqual(serialized["attempt"], 2)
        self.assertEqual(serialized["payload"], payload)

    def test_serialize_command_payload_none(self):
        serialized = self.publisher.serialize_command(
            service="shipping",
            command_type="DespacharPedido",
            saga_id="saga-1",
            command_id="cmd-1",
            attempt=1,
            payload=None,
        )
        self.assertEqual(serialized["payload"], {})

    async def test_publish_command_envia_ao_exchange_com_routing_key(self):
        saga_id = str(uuid.uuid4())
        command_id = str(uuid.uuid4())
        payload = {"items": [{"sku": "A1", "quantity": 2}]}

        result = await self.publisher.publish_command(
            service="inventory",
            command_type="ReservarEstoque",
            saga_id=saga_id,
            command_id=command_id,
            attempt=1,
            payload=payload,
        )

        self.assertEqual(len(self.exchange.published_messages), 1)
        item = self.exchange.published_messages[0]

        # Roteamento direto por nome do serviço
        self.assertEqual(item["routing_key"], "inventory")

        # Conteúdo da mensagem
        msg = item["message"]
        self.assertEqual(msg.content_type, "application/json")
        self.assertEqual(msg.correlation_id, command_id)
        self.assertEqual(msg.headers["saga_id"], saga_id)
        self.assertEqual(msg.headers["command_type"], "ReservarEstoque")
        self.assertEqual(msg.headers["attempt"], 1)
        self.assertEqual(msg.headers["service"], "inventory")

        # Corpo JSON deserializado
        body = json.loads(msg.body.decode("utf-8"))
        self.assertEqual(body["command_id"], command_id)
        self.assertEqual(body["saga_id"], saga_id)
        self.assertEqual(body["command_type"], "ReservarEstoque")
        self.assertEqual(body["payload"], payload)

    async def test_publish_command_servicos_diferentes(self):
        services = [
            ("inventory", "ReservarEstoque"),
            ("payment", "ProcessarPagamento"),
            ("shipping", "DespacharPedido"),
            ("notification", "NotificarCliente"),
        ]

        for srv, cmd in services:
            await self.publisher.publish_command(
                service=srv,
                command_type=cmd,
                saga_id="s1",
                command_id="c1",
            )

        self.assertEqual(len(self.exchange.published_messages), 4)
        routing_keys = [p["routing_key"] for p in self.exchange.published_messages]
        self.assertEqual(routing_keys, ["inventory", "payment", "shipping", "notification"])

    async def test_integracao_com_saga_engine(self):
        session = MockSession()
        engine = SagaEngine(
            session_factory=None,
            workflow=ORDER_WORKFLOW,
            publisher=self.publisher,
        )

        saga = await engine.start_saga(
            order_id="ORD-PUB-TEST",
            payload={"order_id": "ORD-PUB-TEST", "total_amount": 50.0},
            session=session,
        )

        # O engine deve ter acionado o publisher para o Step 0 (inventory)
        self.assertEqual(len(self.exchange.published_messages), 1)
        pub = self.exchange.published_messages[0]
        self.assertEqual(pub["routing_key"], "inventory")

        body = json.loads(pub["message"].body.decode("utf-8"))
        self.assertEqual(body["command_type"], "ReservarEstoque")
        self.assertEqual(body["command_id"], saga.steps[0].command_id)
        self.assertEqual(body["saga_id"], str(saga.id))


if __name__ == "__main__":
    unittest.main()

