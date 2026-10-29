"""
Testes Unitários para Logs Estruturados com Contexto da Saga — Card 7.4.

Valida que:
  - O logger emite strings JSON válidas contendo saga_id, step_name, command_id e attempt
  - contextvars.ContextVar propaga o contexto em corrotinas assíncronas sem poluir assinaturas
  - Tarefas assíncronas concorrentes mantêm seus contextos estritamente isolados
  - O context manager saga_context restaura o contexto prévio ao sair do bloco with
  - Exceções são serializadas com traceback no campo 'exception' do JSON
"""
import asyncio
import io
import json
import logging
import os
import sys
import unittest
import uuid

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ORCHESTRATOR_ROOT = os.path.join(PROJECT_ROOT, "orchestrator")
if ORCHESTRATOR_ROOT not in sys.path:
    sys.path.insert(0, ORCHESTRATOR_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.structured_logging import (
    JSONFormatter,
    clear_saga_context,
    get_saga_context,
    saga_context,
    set_saga_context,
)


class TestJSONFormatter(unittest.TestCase):

    def setUp(self):
        clear_saga_context()
        self.formatter = JSONFormatter()

    def tearDown(self):
        clear_saga_context()

    def test_emissao_json_valido_com_campos_basicos(self):
        """O log formatado deve ser um JSON válido contendo os campos essenciais."""
        record = logging.LogRecord(
            name="test-logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Mensagem simples de teste",
            args=(),
            exc_info=None,
        )

        output = self.formatter.format(record)
        data = json.loads(output)

        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["logger"], "test-logger")
        self.assertEqual(data["message"], "Mensagem simples de teste")
        self.assertIn("timestamp", data)
        self.assertIsNone(data["saga_id"])
        self.assertIsNone(data["step_name"])
        self.assertIsNone(data["command_id"])
        self.assertIsNone(data["attempt"])

    def test_emissao_com_campos_contextuais(self):
        """O log formatado deve incluir os campos de contexto definidos via ContextVar."""
        saga_id = str(uuid.uuid4())
        cmd_id = str(uuid.uuid4())

        set_saga_context(
            saga_id=saga_id,
            step_name="ReservarEstoque",
            command_id=cmd_id,
            attempt=2,
        )

        record = logging.LogRecord(
            name="saga-engine",
            level=logging.WARNING,
            pathname="engine.py",
            lineno=42,
            msg="Aviso na execução do step",
            args=(),
            exc_info=None,
        )

        output = self.formatter.format(record)
        data = json.loads(output)

        self.assertEqual(data["saga_id"], saga_id)
        self.assertEqual(data["step_name"], "ReservarEstoque")
        self.assertEqual(data["command_id"], cmd_id)
        self.assertEqual(data["attempt"], 2)

    def test_log_com_exception_formata_traceback(self):
        """Erros capturados com exc_info devem incluir campo 'exception' com traceback."""
        try:
            raise ValueError("Falha intencional para teste")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test-error",
            level=logging.ERROR,
            pathname="test.py",
            lineno=99,
            msg="Erro ao processar mensagem",
            args=(),
            exc_info=exc_info,
        )

        output = self.formatter.format(record)
        data = json.loads(output)

        self.assertEqual(data["level"], "ERROR")
        self.assertIn("exception", data)
        self.assertIn("Falha intencional para teste", data["exception"])


class TestContextVarsPropagation(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        clear_saga_context()

    def tearDown(self):
        clear_saga_context()

    def test_set_e_clear_saga_context(self):
        """set_saga_context define os valores e clear_saga_context reseta todos para None."""
        set_saga_context(saga_id="saga-1", step_name="step-1", command_id="cmd-1", attempt=1)
        ctx = get_saga_context()
        self.assertEqual(ctx["saga_id"], "saga-1")
        self.assertEqual(ctx["step_name"], "step-1")
        self.assertEqual(ctx["command_id"], "cmd-1")
        self.assertEqual(ctx["attempt"], 1)

        clear_saga_context()
        ctx_cleared = get_saga_context()
        self.assertIsNone(ctx_cleared["saga_id"])
        self.assertIsNone(ctx_cleared["step_name"])
        self.assertIsNone(ctx_cleared["command_id"])
        self.assertIsNone(ctx_cleared["attempt"])

    def test_context_manager_saga_context_escopo_e_restauracao(self):
        """saga_context define valores no bloco with e restaura os valores anteriores ao sair."""
        set_saga_context(saga_id="saga-origem", step_name="step-origem")

        with saga_context(saga_id="saga-temporaria", step_name="step-temp", attempt=3):
            inner_ctx = get_saga_context()
            self.assertEqual(inner_ctx["saga_id"], "saga-temporaria")
            self.assertEqual(inner_ctx["step_name"], "step-temp")
            self.assertEqual(inner_ctx["attempt"], 3)

        outer_ctx = get_saga_context()
        self.assertEqual(outer_ctx["saga_id"], "saga-origem")
        self.assertEqual(outer_ctx["step_name"], "step-origem")
        self.assertIsNone(outer_ctx["attempt"])

    async def test_isolamento_entre_tasks_assincronas_concorrentes(self):
        """Duas corrotinas rodando em paralelo mantêm seus contextos estritamente isolados."""
        results = {}

        async def worker_a():
            with saga_context(saga_id="SAGA-A", step_name="Step-A", attempt=1):
                await asyncio.sleep(0.02)
                results["A"] = get_saga_context()

        async def worker_b():
            with saga_context(saga_id="SAGA-B", step_name="Step-B", attempt=2):
                await asyncio.sleep(0.01)
                results["B"] = get_saga_context()

        await asyncio.gather(worker_a(), worker_b())

        self.assertEqual(results["A"]["saga_id"], "SAGA-A")
        self.assertEqual(results["A"]["step_name"], "Step-A")
        self.assertEqual(results["A"]["attempt"], 1)

        self.assertEqual(results["B"]["saga_id"], "SAGA-B")
        self.assertEqual(results["B"]["step_name"], "Step-B")
        self.assertEqual(results["B"]["attempt"], 2)


class TestLoggerIntegrationWithStream(unittest.TestCase):

    def setUp(self):
        clear_saga_context()
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(JSONFormatter())
        self.test_logger = logging.getLogger("test-stream-logger")
        self.test_logger.setLevel(logging.INFO)
        self.test_logger.addHandler(self.handler)

    def tearDown(self):
        self.test_logger.removeHandler(self.handler)
        clear_saga_context()

    def test_logger_emite_linha_json_completa_no_stream(self):
        """Ao chamar logger.info dentro do contexto, a saída é JSON formatado com os metadados."""
        with saga_context(saga_id="SAGA-999", step_name="DespacharPedido", command_id="CMD-999", attempt=1):
            self.test_logger.info("Despacho iniciado com sucesso")

        raw_output = self.stream.getvalue().strip()
        data = json.loads(raw_output)

        self.assertEqual(data["logger"], "test-stream-logger")
        self.assertEqual(data["message"], "Despacho iniciado com sucesso")
        self.assertEqual(data["saga_id"], "SAGA-999")
        self.assertEqual(data["step_name"], "DespacharPedido")
        self.assertEqual(data["command_id"], "CMD-999")
        self.assertEqual(data["attempt"], 1)


if __name__ == "__main__":
    unittest.main()

