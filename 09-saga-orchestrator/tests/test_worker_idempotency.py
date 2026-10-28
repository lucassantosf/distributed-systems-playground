"""
Testes de Idempotência dos Workers — Card 6.2: Serviços Mockados Idempotentes.

Valida que:
  - Cada worker mantém um dicionário {command_id: reply_payload}.
  - Se um command_id já visto chegar, o worker retorna o resultado anterior sem re-executar a lógica de negócio.
  - A publicação da resposta duplicada ocorre normalmente com os dados cacheados.
  - Um novo command_id executa a regra de negócio normalmente.
  - Cobre os 4 workers: Inventory, Payment, Shipping e Notification.
"""
import asyncio
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.inventory import idempotency_store as inventory_store
from services.inventory import worker as inventory_worker

from services.payment import idempotency_store as payment_store
from services.payment import worker as payment_worker

from services.shipping import idempotency_store as shipping_store
from services.shipping import worker as shipping_worker

from services.notification import idempotency_store as notification_store
from services.notification import worker as notification_worker


class _MockMessageContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockIncomingMessage:
    """Simula um aio_pika.IncomingMessage com payload serializado."""

    def __init__(self, data: dict):
        self.body = json.dumps(data).encode("utf-8")

    def process(self):
        return _MockMessageContext()


class MockExchange:
    def __init__(self):
        self.messages: list[tuple[any, str]] = []

    async def publish(self, message, routing_key: str):
        self.messages.append((message, routing_key))


class MockChannel:
    def __init__(self):
        self.default_exchange = MockExchange()


class TestIdempotencyStoreDirect(unittest.TestCase):
    """Testa os métodos isolados do módulo idempotency_store."""

    def setUp(self):
        inventory_store.clear()

    def tearDown(self):
        inventory_store.clear()

    def test_get_retorna_none_para_id_desconhecido(self):
        self.assertIsNone(inventory_store.get("id-inexistente"))

    def test_save_e_recuperacao(self):
        payload = {"status": "ok", "items": 2}
        inventory_store.save("cmd-123", payload)
        self.assertEqual(inventory_store.get("cmd-123"), payload)

    def test_size_e_clear(self):
        self.assertEqual(inventory_store.size(), 0)
        inventory_store.save("cmd-1", {"a": 1})
        inventory_store.save("cmd-2", {"b": 2})
        self.assertEqual(inventory_store.size(), 2)
        inventory_store.clear()
        self.assertEqual(inventory_store.size(), 0)


class TestWorkerIdempotencyProcessMessage(unittest.IsolatedAsyncioTestCase):
    """Testa o process_message de cada worker garantindo que não re-executam regras."""

    def setUp(self):
        inventory_store.clear()
        payment_store.clear()
        shipping_store.clear()
        notification_store.clear()

    def tearDown(self):
        inventory_store.clear()
        payment_store.clear()
        shipping_store.clear()
        notification_store.clear()

    async def test_inventory_worker_idempotente(self):
        """Inventory worker não deve re-executar regras para mesmo command_id."""
        channel = MockChannel()
        cmd_id = "inv-cmd-001"
        data = {
            "command_id": cmd_id,
            "saga_id": "saga-1",
            "command_type": "ReservarEstoque",
            "payload": {"order_id": "ord-1", "items": [{"sku": "PROD-1"}]},
            "attempt": 1,
        }

        with patch("services.inventory.worker.apply_business_rules", wraps=inventory_worker.apply_business_rules) as spy_rules:
            # 1ª Execução
            msg1 = MockIncomingMessage(data)
            await inventory_worker.process_message(msg1, channel)

            self.assertEqual(spy_rules.call_count, 1)
            self.assertEqual(len(channel.default_exchange.messages), 1)
            reply1 = json.loads(channel.default_exchange.messages[0][0].body.decode())
            self.assertTrue(reply1["success"])
            self.assertEqual(reply1["command_id"], cmd_id)

            # 2ª Execução com MESMO command_id
            msg2 = MockIncomingMessage(data)
            await inventory_worker.process_message(msg2, channel)

            # A regra NÃO deve ter sido chamada novamente!
            self.assertEqual(spy_rules.call_count, 1)
            self.assertEqual(len(channel.default_exchange.messages), 2)
            reply2 = json.loads(channel.default_exchange.messages[1][0].body.decode())
            self.assertEqual(reply1, reply2)

            # 3ª Execução com NOVO command_id
            data3 = dict(data, command_id="inv-cmd-002")
            msg3 = MockIncomingMessage(data3)
            await inventory_worker.process_message(msg3, channel)

            # A regra DEVE ser chamada para o novo command_id
            self.assertEqual(spy_rules.call_count, 2)
            self.assertEqual(len(channel.default_exchange.messages), 3)

    async def test_payment_worker_idempotente(self):
        """Payment worker não deve re-executar regras para mesmo command_id."""
        channel = MockChannel()
        cmd_id = "pay-cmd-001"
        data = {
            "command_id": cmd_id,
            "saga_id": "saga-2",
            "command_type": "ProcessarPagamento",
            "payload": {"order_id": "ord-2", "total_amount": 100.0},
            "attempt": 1,
        }

        with patch("services.payment.worker.apply_business_rules", wraps=payment_worker.apply_business_rules) as spy_rules:
            # 1ª Execução
            msg1 = MockIncomingMessage(data)
            await payment_worker.process_message(msg1, channel)
            self.assertEqual(spy_rules.call_count, 1)

            # 2ª Execução duplicada
            msg2 = MockIncomingMessage(data)
            await payment_worker.process_message(msg2, channel)
            self.assertEqual(spy_rules.call_count, 1)

            reply1 = json.loads(channel.default_exchange.messages[0][0].body.decode())
            reply2 = json.loads(channel.default_exchange.messages[1][0].body.decode())
            self.assertEqual(reply1, reply2)

    async def test_shipping_worker_idempotente(self):
        """Shipping worker não deve re-executar regras para mesmo command_id."""
        channel = MockChannel()
        cmd_id = "ship-cmd-001"
        data = {
            "command_id": cmd_id,
            "saga_id": "saga-3",
            "command_type": "DespacharPedido",
            "payload": {"order_id": "ord-3", "shipping_address": "Rua 1"},
            "attempt": 1,
        }

        with patch("services.shipping.worker.apply_business_rules", wraps=shipping_worker.apply_business_rules) as spy_rules:
            # 1ª Execução
            msg1 = MockIncomingMessage(data)
            await shipping_worker.process_message(msg1, channel)
            self.assertEqual(spy_rules.call_count, 1)

            # 2ª Execução duplicada
            msg2 = MockIncomingMessage(data)
            await shipping_worker.process_message(msg2, channel)
            self.assertEqual(spy_rules.call_count, 1)

            reply1 = json.loads(channel.default_exchange.messages[0][0].body.decode())
            reply2 = json.loads(channel.default_exchange.messages[1][0].body.decode())
            self.assertEqual(reply1, reply2)

    async def test_notification_worker_idempotente(self):
        """Notification worker não deve re-executar regras para mesmo command_id."""
        channel = MockChannel()
        cmd_id = "notif-cmd-001"
        data = {
            "command_id": cmd_id,
            "saga_id": "saga-4",
            "command_type": "NotificarCliente",
            "payload": {"customer_id": "c-1", "message": "Olá"},
            "attempt": 1,
        }

        with patch("services.notification.worker.apply_business_rules", wraps=notification_worker.apply_business_rules) as spy_rules:
            # 1ª Execução
            msg1 = MockIncomingMessage(data)
            await notification_worker.process_message(msg1, channel)
            self.assertEqual(spy_rules.call_count, 1)

            # 2ª Execução duplicada
            msg2 = MockIncomingMessage(data)
            await notification_worker.process_message(msg2, channel)
            self.assertEqual(spy_rules.call_count, 1)

            reply1 = json.loads(channel.default_exchange.messages[0][0].body.decode())
            reply2 = json.loads(channel.default_exchange.messages[1][0].body.decode())
            self.assertEqual(reply1, reply2)


if __name__ == "__main__":
    unittest.main()

