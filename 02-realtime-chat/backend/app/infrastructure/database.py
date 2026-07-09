import asyncpg
from app.config import settings


async def get_db_connection():
    return await asyncpg.connect(settings.database_url)


async def ensure_schema():
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                room VARCHAR(100) NOT NULL,
                username VARCHAR(100) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
    finally:
        await conn.close()


async def test_connection():
    try:
        conn = await get_db_connection()
        version = await conn.fetchval("SELECT version()")
        await conn.close()
        return True, version
    except Exception as e:
        return False, str(e)
