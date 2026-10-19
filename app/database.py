from collections.abc import Generator
from importlib import import_module

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    database_session = SessionLocal()
    try:
        yield database_session
    finally:
        database_session.close()


def create_tables() -> None:
    import_module("app.models")
    Base.metadata.create_all(bind=engine)
