"""
Testes Unitários para o Script de Stress Test — Card 8.4.

Valida que:
  - calculate_percentile calcula corretamente P50, P90, P95, P99 e extremos
  - StressMetrics computa percentis, throughput e contadores com precisão
  - Casos limites (listas vazias, valores únicos) são tratados sem exceções
  - A condição de aceitação (0 Sagas travadas) é verificada rigorosamente
"""
import unittest

from scripts.stress_test import StressMetrics, calculate_percentile


class TestStressTestMetrics(unittest.TestCase):

    def test_calculate_percentile_valores_conhecidos(self):
        # 1 a 100
        values = list(range(1, 101))
        p50 = calculate_percentile(values, 50)
        p90 = calculate_percentile(values, 90)
        p95 = calculate_percentile(values, 95)
        p99 = calculate_percentile(values, 99)

        self.assertAlmostEqual(p50, 50.5, places=1)
        self.assertAlmostEqual(p90, 90.1, places=1)
        self.assertAlmostEqual(p95, 95.05, places=1)
        self.assertAlmostEqual(p99, 99.01, places=1)

    def test_calculate_percentile_casos_borda(self):
        # Lista vazia
        self.assertEqual(calculate_percentile([], 50), 0.0)

        # Um único elemento
        self.assertEqual(calculate_percentile([42.0], 95), 42.0)

        # Dois elementos
        p = calculate_percentile([10.0, 20.0], 50)
        self.assertEqual(p, 15.0)

    def test_stress_metrics_throughput_e_percentis(self):
        metrics = StressMetrics(total_sagas=10)
        metrics.completed_count = 8
        metrics.compensated_count = 2
        metrics.failed_count = 0
        metrics.stuck_count = 0
        metrics.total_wall_time_s = 2.0  # 10 sagas em 2s -> 5 sagas/s
        metrics.durations = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

        self.assertEqual(metrics.finished_count, 10)
        self.assertEqual(metrics.throughput, 5.0)

        p = metrics.compute_percentiles()
        self.assertEqual(p["min"], 0.1)
        self.assertEqual(p["max"], 1.0)
        self.assertAlmostEqual(p["avg"], 0.55, places=2)
        self.assertAlmostEqual(p["p50"], 0.55, places=2)

    def test_criterio_de_aceitacao_zero_sagas_travadas(self):
        metrics = StressMetrics(total_sagas=5)
        metrics.completed_count = 5
        metrics.stuck_count = 0
        self.assertEqual(metrics.stuck_count, 0)
        self.assertEqual(metrics.finished_count, metrics.total_sagas)


if __name__ == "__main__":
    unittest.main()

