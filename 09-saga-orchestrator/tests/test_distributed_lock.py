"""
Testes Unitários para Lock Distribuído e Sagas Concorrentes — Card 8.3.

Valida que:
  - RedisDistributedLock executa SET NX EX para adquirir o lock
  - Quando a chave já está em uso, acquire respeita o timeout e retorna False
  - release remove a chave apenas se o token for correspondente (script Lua atômico)
  - O context manager lock garante acquire e release determinísticos
  - Múltiplas tarefas concorrentes competindo pela mesma chave são serializadas pelo lock
  - Fallback gracioso opera normalmente quando Redis não está disponível
"""
import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ORCHESTRATOR_ROOT = os.path.join(PROJECT_ROOT, "orchestrator")
if ORCHESTRATOR_ROOT not in sys.path:
    sys.path.insert(0, ORCHESTRATOR_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.distributed_lock import RedisDistributedLock


class MockRedisClient:
    """Emula cliente Redis assíncrono em memória com suporte a SET NX EX e eval Lua."""

    def __init__(self):
        self.data = {}

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.data:
            return None
        self.data[key] = value
        return True

    async def get(self, key):
        return self.data.get(key)

    async def delete(self, key):
        return self.data.pop(key, None) is not None

    async def eval(self, script, numkeys, key, arg):
        # Emula o script de liberação segura: if get(key) == arg then del(key) return 1 else return 0
        if self.data.get(key) == arg:
            self.data.pop(key, None)
            return 1
        return 0


class TestDistributedLock(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_redis = MockRedisClient()
        self.lock_manager = RedisDistributedLock(redis_client=self.mock_redis)

    async def test_acquire_e_release_com_sucesso(self):
        """Adquire o lock com SET NX e libera com token correto."""
        key = "cmd-123"
        token = "token-abc"

        # 1. Adquire
        acquired = await self.lock_manager.acquire(key, token, expire_seconds=10)
        self.assertTrue(acquired)
        self.assertEqual(self.mock_redis.data.get(f"lock:{key}"), token)

        # 2. Libera
        released = await self.lock_manager.release(key, token)
        self.assertTrue(released)
        self.assertNotIn(f"lock:{key}", self.mock_redis.data)

    async def test_acquire_falha_se_chave_ocupada_e_atinge_timeout(self):
        """Se a chave já estiver ocupada por outro token, acquire retorna False após o wait_timeout."""
        key = "cmd-busy"
        self.mock_redis.data[f"lock:{key}"] = "outro-token"

        acquired = await self.lock_manager.acquire(
            key, "meu-token", expire_seconds=5, wait_timeout_seconds=0.1, retry_interval_seconds=0.02
        )
        self.assertFalse(acquired)

    async def test_release_com_token_diferente_nao_deleta_lock_alheio(self):
        """Se o lock expirou e outro processo assumiu a chave, release não deve apagar o lock do outro."""
        key = "cmd-steal"
        self.mock_redis.data[f"lock:{key}"] = "token-do-processo-b"

        # Processo A tenta liberar com seu token antigo
        released = await self.lock_manager.release(key, "token-do-processo-a")
        self.assertFalse(released)
        self.assertEqual(self.mock_redis.data.get(f"lock:{key}"), "token-do-processo-b")

    async def test_context_manager_adquire_e_libera_automaticamente(self):
        """O bloco async with distributed_lock.lock(...) gerencia o ciclo completo."""
        key = "cmd-ctx"
        async with self.lock_manager.lock(key, expire_seconds=5) as acq:
            self.assertTrue(acq)
            self.assertIn(f"lock:{key}", self.mock_redis.data)

        self.assertNotIn(f"lock:{key}", self.mock_redis.data)

    async def test_concorrencia_duas_tasks_competindo_pelo_mesmo_lock(self):
        """Duas tasks concorrentes executando com lock: a segunda aguarda a primeira terminar."""
        key = "cmd-concorrente"
        ordem_execucao = []

        async def worker_1():
            async with self.lock_manager.lock(key, expire_seconds=5, wait_timeout_seconds=1.0):
                ordem_execucao.append("w1_start")
                await asyncio.sleep(0.05)
                ordem_execucao.append("w1_end")

        async def worker_2():
            await asyncio.sleep(0.01)  # Garante que worker_1 entra primeiro
            async with self.lock_manager.lock(key, expire_seconds=5, wait_timeout_seconds=1.0):
                ordem_execucao.append("w2_start")
                await asyncio.sleep(0.02)
                ordem_execucao.append("w2_end")

        await asyncio.gather(worker_1(), worker_2())

        self.assertEqual(ordem_execucao, ["w1_start", "w1_end", "w2_start", "w2_end"])

    async def test_fallback_quando_redis_indisponivel(self):
        """Quando o cliente Redis for None, o lock retorna True sem travar a aplicação."""
        lock_sem_redis = RedisDistributedLock(redis_client=None)
        # Mock do get_client retornando None
        lock_sem_redis.get_client = AsyncMock(return_value=None)

        async with lock_sem_redis.lock("key-qualquer") as acq:
            self.assertTrue(acq)


if __name__ == "__main__":
    unittest.main()

