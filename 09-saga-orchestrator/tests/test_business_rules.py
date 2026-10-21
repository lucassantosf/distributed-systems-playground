"""
Unit tests para as regras de negócio determinísticas (Card 1.3)
Testa diretamente os módulos isolados services/*/rules.py usando unittest da biblioteca padrão.
Não requer RabbitMQ, Docker ou bibliotecas de terceiros.
"""
import os
import sys
import unittest

# Adiciona o diretório raiz do projeto ao sys.path para imports limpos
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.inventory.rules import apply_business_rules as inventory_rules
from services.payment.rules import apply_business_rules as payment_rules
from services.shipping.rules import apply_business_rules as shipping_rules
from services.notification.rules import apply_business_rules as notification_rules


class TestBusinessRules(unittest.TestCase):

    # 1. Inventory Rules
    def test_inventory_happy_path(self):
        payload = {"order_id": "ord-1", "items": [{"sku": "PROD-1"}, {"sku": "PROD-2"}]}
        success, result, error = inventory_rules("ReservarEstoque", payload)
        self.assertTrue(success)
        self.assertEqual(result, {"reserved_items": 2})
        self.assertIsNone(error)

    def test_inventory_out_of_stock_fails(self):
        payload = {"order_id": "ord-1", "items": [{"sku": "PROD-ESGOTADO-123"}]}
        success, result, error = inventory_rules("ReservarEstoque", payload)
        self.assertFalse(success)
        self.assertIn("esgotado", error.lower())

    def test_inventory_compensation_success(self):
        payload = {"order_id": "ord-1"}
        success, result, error = inventory_rules("LiberarEstoque", payload)
        self.assertTrue(success)
        self.assertEqual(result, {"status": "stock_released"})
        self.assertIsNone(error)

    def test_inventory_compensation_failure_scenario_66(self):
        payload = {"order_id": "ord-uuid-66"}
        success, result, error = inventory_rules("LiberarEstoque", payload)
        self.assertFalse(success)
        self.assertIn("falha fatal", error.lower())

    # 2. Payment Rules
    def test_payment_happy_path(self):
        payload = {"order_id": "ord-1", "total_amount": 250.0}
        success, result, error = payment_rules("ProcessarPagamento", payload)
        self.assertTrue(success)
        self.assertEqual(result.get("status"), "approved")
        self.assertIsNone(error)

    def test_payment_refused_amount_limit(self):
        payload = {"order_id": "ord-1", "total_amount": 10000.0}
        success, result, error = payment_rules("ProcessarPagamento", payload)
        self.assertFalse(success)
        self.assertIn("limite de crédito", error.lower())

    def test_payment_transient_failure_scenario_77(self):
        payload = {"order_id": "ord-77", "total_amount": 100.0}

        # Tentativa 1 -> falha
        s1, _, err1 = payment_rules("ProcessarPagamento", payload, attempt=1)
        self.assertFalse(s1)
        self.assertIn("tentativa 1/3", err1)

        # Tentativa 2 -> falha
        s2, _, err2 = payment_rules("ProcessarPagamento", payload, attempt=2)
        self.assertFalse(s2)
        self.assertIn("tentativa 2/3", err2)

        # Tentativa 3 -> sucesso
        s3, res3, err3 = payment_rules("ProcessarPagamento", payload, attempt=3)
        self.assertTrue(s3)
        self.assertEqual(res3.get("status"), "approved")
        self.assertIsNone(err3)

    def test_payment_compensation(self):
        payload = {"order_id": "ord-1"}
        success, result, error = payment_rules("EstornarPagamento", payload)
        self.assertTrue(success)
        self.assertEqual(result.get("status"), "refunded")
        self.assertIsNone(error)

    # 3. Shipping Rules
    def test_shipping_dispatch_success(self):
        payload = {"order_id": "abcdef123456"}
        success, result, error = shipping_rules("DespacharPedido", payload)
        self.assertTrue(success)
        self.assertEqual(result.get("tracking_code"), "TRK-ABCDEF12")
        self.assertIsNone(error)

    def test_shipping_compensation_success(self):
        payload = {"order_id": "ord-1"}
        success, result, error = shipping_rules("CancelarDespacho", payload)
        self.assertTrue(success)
        self.assertEqual(result, {"status": "shipping_cancelled"})
        self.assertIsNone(error)

    # 4. Notification Rules
    def test_notification_always_success(self):
        payload = {"customer_id": "cust-123"}
        success, result, error = notification_rules("NotificarCliente", payload)
        self.assertTrue(success)
        self.assertEqual(result, {"notified": True, "customer_id": "cust-123"})
        self.assertIsNone(error)

    # 5. Unknown Commands (Validação de isolamento de filas e handlers)
    def test_inventory_unknown_command_returns_false(self):
        success, result, error = inventory_rules("ComandoInvalido", {})
        self.assertFalse(success)
        self.assertIn("não suportado", error)

    def test_payment_unknown_command_returns_false(self):
        success, result, error = payment_rules("ComandoInvalido", {})
        self.assertFalse(success)
        self.assertIn("não suportado", error)

    def test_shipping_unknown_command_returns_false(self):
        success, result, error = shipping_rules("ComandoInvalido", {})
        self.assertFalse(success)
        self.assertIn("não suportado", error)

    def test_notification_unknown_command_returns_false(self):
        success, result, error = notification_rules("ComandoInvalido", {})
        self.assertFalse(success)
        self.assertIn("não suportado", error)


if __name__ == "__main__":
    unittest.main()

