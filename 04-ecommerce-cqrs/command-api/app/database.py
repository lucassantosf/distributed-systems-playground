from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(engine)


class Base(DeclarativeBase):
    pass


def init_db():
    import models
    Base.metadata.create_all(bind=engine)
