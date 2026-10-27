"""
Testes unitários para Card 5.4 — Configuração por Variáveis de Ambiente.

Cobre:
  - Defaults razoáveis de produção (STEP_TIMEOUT_SECONDS=30, STEP_MAX_ATTEMPTS=3, RETRY_BASE_DELAY_SECONDS=1.0)
  - Carregamento de variáveis de ambiente via load_env_defaults()
  - Factory create_order_workflow com parâmetros customizados
  - Propagação das configurações de timeout e attempts para os StepDefinitions
  - Integração com o SagaEngine respeitando os parâmetros do workflow
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))

from app.core.workflow import (
    DEFAULT_STEP_TIMEOUT_SECONDS,
    DEFAULT_STEP_MAX_ATTEMPTS,
    DEFAULT_RETRY_BASE_DELAY,
    load_env_defaults,
    create_order_workflow,
    StepDefinition,
    WorkflowDefinition,
)
from app.core.engine import SagaEngine

try:
    from app.config import Settings
    HAS_PYDANTIC_SETTINGS = True
except ImportError:
    HAS_PYDANTIC_SETTINGS = False


class TestConfiguracaoVariaveisAmbiente(unittest.TestCase):

    def test_load_env_defaults_producao(self):
        """
        load_env_defaults() deve retornar defaults de produção razoáveis
        quando nenhuma variável de ambiente estiver definida.
        """
        with patch.dict(os.environ, {}, clear=True):
            defaults = load_env_defaults()
            self.assertEqual(defaults["STEP_TIMEOUT_SECONDS"], 30)
            self.assertEqual(defaults["STEP_MAX_ATTEMPTS"], 3)
            self.assertEqual(defaults["RETRY_BASE_DELAY_SECONDS"], 1.0)

    def test_load_env_defaults_customizado_via_ambiente(self):
        """
        load_env_defaults() deve ler STEP_TIMEOUT_SECONDS, STEP_MAX_ATTEMPTS
        e RETRY_BASE_DELAY_SECONDS a partir de os.environ.
        """
        env = {
            "STEP_TIMEOUT_SECONDS": "5",
            "STEP_MAX_ATTEMPTS": "4",
            "RETRY_BASE_DELAY_SECONDS": "0.5",
        }
        with patch.dict(os.environ, env, clear=True):
            custom = load_env_defaults()
            self.assertEqual(custom["STEP_TIMEOUT_SECONDS"], 5)
            self.assertEqual(custom["STEP_MAX_ATTEMPTS"], 4)
            self.assertEqual(custom["RETRY_BASE_DELAY_SECONDS"], 0.5)

    def test_factory_create_order_workflow_valores_customizados(self):
        """
        create_order_workflow deve permitir customização explícita de
        timeout_seconds e max_attempts para todos os steps.
        """
        wf = create_order_workflow(step_timeout_seconds=8, step_max_attempts=4)
        self.assertEqual(wf.name, "ProcessarPedido")
        self.assertEqual(wf.total_steps, 4)

        for step in wf.steps:
            self.assertEqual(step.timeout_seconds, 8)
            self.assertEqual(step.max_attempts, 4)

    def test_factory_create_order_workflow_usa_defaults(self):
        """
        create_order_workflow sem argumentos deve usar as constantes configuradas.
        """
        wf = create_order_workflow()
        for step in wf.steps:
            self.assertEqual(step.timeout_seconds, DEFAULT_STEP_TIMEOUT_SECONDS)
            self.assertEqual(step.max_attempts, DEFAULT_STEP_MAX_ATTEMPTS)

    def test_workflow_acelera_no_ambiente_docker(self):
        """
        Valida que valores acelerados típicos do docker-compose (ex: timeout=5s, delay=0.5s)
        são atribuídos com sucesso ao workflow gerado.
        """
        wf_rapido = create_order_workflow(step_timeout_seconds=5, step_max_attempts=3)
        for step in wf_rapido.steps:
            self.assertEqual(step.timeout_seconds, 5)
            self.assertEqual(step.max_attempts, 3)

    def test_engine_utiliza_workflow_configurado(self):
        """
        SagaEngine deve aceitar qualquer WorkflowDefinition configurado,
        respeitando os timeouts e attempts daquele workflow.
        """
        custom_wf = create_order_workflow(step_timeout_seconds=12, step_max_attempts=2)
        engine = SagaEngine(workflow=custom_wf)

        step_def_0 = engine.workflow.get_step_by_index(0)
        self.assertEqual(step_def_0.timeout_seconds, 12)
        self.assertEqual(step_def_0.max_attempts, 2)

    @unittest.skipUnless(HAS_PYDANTIC_SETTINGS, "pydantic_settings não disponível no ambiente")
    def test_settings_pydantic_defaults(self):
        """Testa defaults de Settings quando pydantic_settings estiver instalado."""
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            self.assertEqual(s.STEP_TIMEOUT_SECONDS, 30)
            self.assertEqual(s.STEP_MAX_ATTEMPTS, 3)
            self.assertEqual(s.RETRY_BASE_DELAY_SECONDS, 1.0)


if __name__ == "__main__":
    unittest.main()

