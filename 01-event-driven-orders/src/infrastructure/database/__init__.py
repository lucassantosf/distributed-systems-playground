from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from src.settings import settings

DATABASE_URL = settings.DATABASE_URL

# synchronous engine (simple for local development)
engine = create_engine(DATABASE_URL, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

from src.modules.orders.models import Order  # noqa: F401, E402
from src.modules.email_logs.models import EmailLog  # noqa: F401, E402


def init_db():
    """Create database tables from models (only for local/dev use).

    This will retry a few times to allow a freshly started Postgres container
    to become ready when using Docker Compose.
    """
    import time
    from sqlalchemy import text

    max_retries = 10
    for attempt in range(max_retries):
        try:
            # simple connect test
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except Exception:
            if attempt + 1 == max_retries:
                raise
            time.sleep(1)

    Base.metadata.create_all(bind=engine)
