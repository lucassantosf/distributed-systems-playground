"""
Configuração da conexão com o banco de dados (SQLAlchemy).
DATABASE_URL aponta para db_producer no container postgres.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/db_producer",
)

engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """
    Dependency FastAPI: abre uma sessão e garante fechamento ao fim da request.

    Uso:
        @router.post("/orders")
        def create(db: Session = Depends(get_db)):
            ...
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
