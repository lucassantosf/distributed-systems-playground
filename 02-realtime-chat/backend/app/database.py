import asyncpg
from app.config import settings


async def get_db_connection():
    return await asyncpg.connect(settings.database_url)


async def test_connection():
    try:
        conn = await get_db_connection()
        version = await conn.fetchval("SELECT version()")
        await conn.close()
        return True, version
    except Exception as e:
        return False, str(e)
