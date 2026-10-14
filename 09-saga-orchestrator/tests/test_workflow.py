import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "orchestrator"))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.workflow import ORDER_WORKFLOW, StepDefinition, WorkflowDefinition


class TestWorkflowDefinition(unittest.TestCase):

    def test_workflow_steps_order_and_count(self):
        self.assertEqual(ORDER_WORKFLOW.name, "ProcessarPedido")
        self.assertEqual(ORDER_WORKFLOW.total_steps, 4)

        step_names = [s.name for s in ORDER_WORKFLOW.steps]
        expected_names = [
            "ReservarEstoque",
            "ProcessarPagamento",
            "DespacharPedido",
            "NotificarCliente",
        ]
        self.assertEqual(step_names, expected_names)

    def test_step_services_and_commands(self):
        # Step 0: inventory
        s0 = ORDER_WORKFLOW.get_step_by_index(0)
        self.assertIsNotNone(s0)
        self.assertEqual(s0.service, "inventory")
        self.assertEqual(s0.command_type, "ReservarEstoque")
        self.assertEqual(s0.compensation_command, "LiberarEstoque")
        self.assertTrue(s0.has_compensation)

        # Step 1: payment
        s1 = ORDER_WORKFLOW.get_step_by_index(1)
        self.assertIsNotNone(s1)
        self.assertEqual(s1.service, "payment")
        self.assertEqual(s1.command_type, "ProcessarPagamento")
        self.assertEqual(s1.compensation_command, "EstornarPagamento")
        self.assertTrue(s1.has_compensation)

        # Step 2: shipping
        s2 = ORDER_WORKFLOW.get_step_by_index(2)
        self.assertIsNotNone(s2)
        self.assertEqual(s2.service, "shipping")
        self.assertEqual(s2.command_type, "DespacharPedido")
        self.assertEqual(s2.compensation_command, "CancelarDespacho")
        self.assertTrue(s2.has_compensation)

        # Step 3: notification (fire-and-forget)
        s3 = ORDER_WORKFLOW.get_step_by_index(3)
        self.assertIsNotNone(s3)
        self.assertEqual(s3.service, "notification")
        self.assertEqual(s3.command_type, "NotificarCliente")
        self.assertIsNone(s3.compensation_command)
        self.assertFalse(s3.has_compensation)

    def test_get_step_by_name(self):
        step = ORDER_WORKFLOW.get_step_by_name("ProcessarPagamento")
        self.assertIsNotNone(step)
        self.assertEqual(step.service, "payment")

        step_non_existent = ORDER_WORKFLOW.get_step_by_name("Inexistente")
        self.assertIsNone(step_non_existent)

    def test_get_step_by_invalid_index(self):
        self.assertIsNone(ORDER_WORKFLOW.get_step_by_index(-1))
        self.assertIsNone(ORDER_WORKFLOW.get_step_by_index(99))

    def test_step_immutability(self):
        s0 = ORDER_WORKFLOW.get_step_by_index(0)
        with self.assertRaises(Exception):
            s0.name = "OutroNome"  # Frozen dataclass


if __name__ == "__main__":
    unittest.main()

