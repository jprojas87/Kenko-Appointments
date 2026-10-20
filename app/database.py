from collections.abc import Generator
from importlib import import_module

from sqlalchemy import create_engine, text
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
    migrate_user_id_column(engine)
    Base.metadata.create_all(bind=engine)


def migrate_user_id_column(database_engine=engine) -> None:
    """Convert legacy PostgreSQL UUID user IDs to text without changing their values."""
    if database_engine.dialect.name != "postgresql":
        return

    with database_engine.begin() as connection:
        data_type = connection.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = 'appointments' AND column_name = 'user_id'"
            )
        ).scalar_one_or_none()
        if data_type == "uuid":
            connection.exec_driver_sql(
                "ALTER TABLE appointments ALTER COLUMN user_id TYPE TEXT USING user_id::text"
            )
