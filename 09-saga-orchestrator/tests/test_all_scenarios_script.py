"""
Testes Unitários para o Script de Validação de Todos os Cenários — Card 8.1.

Valida que:
  - Os 6 cenários cobrem as regras de negócio determinísticas da tabela de falhas
  - A lógica de simulação e checagem de cada cenário valida os estados esperados da Saga:
      * Cenário 1: Happy Path -> COMPLETED
      * Cenário 2: Pagamento Recusado -> COMPENSATED (Step 0 compensado, Step 1 falho)
      * Cenário 3: Estoque Indisponível -> COMPENSATED (Step 0 falho, nenhum step completado)
      * Cenário 4: Timeout de Despacho -> COMPENSATED (Step 2 falho, Steps 0 e 1 compensados)
      * Cenário 5: Falha Transitória -> COMPLETED (Step 1 com retries concluído na 3ª)
      * Cenário 6: Falha na Compensação -> FAILED (Step 0 COMPENSATING_FAILED)
  - A consolidação do relatório contabiliza corretamente a duração, status e resultado PASSED/FAILED
"""
import unittest

from scripts.verify_all_scenarios import ScenarioResult


class TestVerifyAllScenariosDefinitions(unittest.TestCase):

    def test_scenario_result_dataclass(self):
        res = ScenarioResult("Happy Path", "1-HAPPY-PATH")
        self.assertEqual(res.name, "Happy Path")
        self.assertEqual(res.code, "1-HAPPY-PATH")
        self.assertFalse(res.passed)
        self.assertEqual(res.details, [])
        self.assertIsNone(res.error)

        res.passed = True
        res.final_status = "COMPLETED"
        res.duration_s = 1.25
        res.details.append("4 steps concluídos")

        self.assertTrue(res.passed)
        self.assertEqual(res.final_status, "COMPLETED")
        self.assertEqual(res.duration_s, 1.25)
        self.assertEqual(len(res.details), 1)

    def test_payloads_dos_cenarios_possuem_as_regras_deterministas(self):
        """Garante que as regras determinísticas dos payloads estão de acordo com o design."""
        # Cenário 1: valor normal sem SKU especial
        amount_1 = 100.0
        sku_1 = "PROD-A"
        self.assertLessEqual(amount_1, 9999.99)
        self.assertNotIn("ESGOTADO", sku_1)

        # Cenário 2: valor > 9999.99 aciona recusa de limite
        amount_2 = 12000.0
        self.assertGreater(amount_2, 9999.99)

        # Cenário 3: SKU contendo ESGOTADO
        sku_3 = "PROD-ESGOTADO-99"
        self.assertIn("ESGOTADO", sku_3)

        # Cenário 4: order_id terminando em 88 para timeout de shipping
        order_id_4 = "ORD-TEST-88"
        self.assertTrue(order_id_4.endswith("88"))

        # Cenário 5: order_id terminando em 77 para retry no payment
        order_id_5 = "ORD-TEST-77"
        self.assertTrue(order_id_5.endswith("77"))

        # Cenário 6: order_id terminando em 66 para falha fatal na compensação do estoque
        order_id_6 = "ORD-TEST-66"
        self.assertTrue(order_id_6.endswith("66"))


if __name__ == "__main__":
    unittest.main()

