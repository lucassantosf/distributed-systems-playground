"""
Lock Distribuído com Redis — Card 8.3: Sagas Concorrentes em Paralelo.

Implementa lock distribuído atômico utilizando o comando:
    SET lock_key lock_value NX EX expire_seconds

Usado em cenários de scale-out do orquestrador (múltiplas réplicas em paralelo)
para garantir que apenas uma instância processe a reply de um dado command_id / saga_id
por vez, prevenindo race conditions em nível distribuído.

Suporta:
  - Adquirir lock com tentativa e expiração configurável (TTL)
  - Liberar lock via script Lua atômico (garante que apenas o detentor libera seu lock)
  - Async context manager para uso idiomático: async with distributed_lock(...)
  - Fallback gracioso caso Redis não esteja configurado ou disponível
"""
import asyncio
from contextlib import asynccontextmanager
import logging
import os
import uuid
from typing import Optional

logger = logging.getLogger("distributed-lock")

try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    aioredis = None
    HAS_REDIS = False


# Script Lua para liberação segura do lock (verifica se o token bate antes de deletar)
_RELEASE_LOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class RedisDistributedLock:
    """
    Gerenciador de Locks Distribuídos com Redis.
    """

    def __init__(self, redis_client=None, redis_url: Optional[str] = None):
        self._client = redis_client
        self._url = redis_url or os.getenv("REDIS_URL", "redis://redis:6379/0")
        self._initialized = False

    async def get_client(self):
        if self._client is not None:
            return self._client

        if not HAS_REDIS:
            return None

        if not self._initialized:
            try:
                self._client = aioredis.from_url(
                    self._url,
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                    socket_timeout=2.0,
                )
                self._initialized = True
            except Exception as e:
                logger.warning(f"Não foi possível inicializar cliente Redis ({e}). Continuando sem lock distribuído.")
                return None

        return self._client

    async def acquire(
        self,
        key: str,
        token: str,
        expire_seconds: int = 10,
        wait_timeout_seconds: float = 3.0,
        retry_interval_seconds: float = 0.05,
    ) -> bool:
        """
        Tenta adquirir o lock com SET NX EX. Se ocupado, faz retry até wait_timeout_seconds.
        """
        client = await self.get_client()
        if client is None:
            # Sem Redis disponível, permite prosseguir (fallback seguro para testes/monólitos)
            return True

        lock_key = f"lock:{key}"
        deadline = asyncio.get_event_loop().time() + wait_timeout_seconds

        while True:
            try:
                # SET key token NX EX expire_seconds
                acquired = await client.set(lock_key, token, nx=True, ex=expire_seconds)
                if acquired:
                    logger.debug(f"[DistributedLock] Lock adquirido: {lock_key} (token={token})")
                    return True
            except Exception as e:
                logger.warning(f"[DistributedLock] Erro ao comunicar com Redis ({e}). Prosseguindo sem lock.")
                return True

            if asyncio.get_event_loop().time() >= deadline:
                logger.warning(f"[DistributedLock] Timeout aguardando lock: {lock_key}")
                return False

            await asyncio.sleep(retry_interval_seconds)

    async def release(self, key: str, token: str) -> bool:
        """
        Libera o lock usando script Lua atômico para evitar deletar lock de outro processo.
        """
        client = await self.get_client()
        if client is None:
            return True

        lock_key = f"lock:{key}"
        try:
            res = await client.eval(_RELEASE_LOCK_LUA, 1, lock_key, token)
            released = bool(res == 1)
            if released:
                logger.debug(f"[DistributedLock] Lock liberado: {lock_key}")
            return released
        except Exception as e:
            logger.warning(f"[DistributedLock] Erro ao liberar lock {lock_key} no Redis: {e}")
            return False

    @asynccontextmanager
    async def lock(
        self,
        key: str,
        expire_seconds: int = 10,
        wait_timeout_seconds: float = 3.0,
    ):
        """Context manager assíncrono para acquire / release seguro."""
        token = str(uuid.uuid4())
        acquired = await self.acquire(
            key,
            token,
            expire_seconds=expire_seconds,
            wait_timeout_seconds=wait_timeout_seconds,
        )
        try:
            yield acquired
        finally:
            if acquired:
                await self.release(key, token)

