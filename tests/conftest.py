import os
from collections.abc import Generator
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, get_db
from app.events.fake_publisher import FakePublisher
from app.events.publisher import get_event_publisher
from app.main import app
from app.models import Appointment, AppointmentType, MedicalCenter, Physician

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://appointments:appointments@localhost:5433/appointments_test",
)
TEST_USER_ID = UUID("0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000")
OTHER_USER_ID = UUID("0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8001")


def _ensure_test_database(url: URL) -> None:
    if not url.database:
        raise ValueError("TEST_DATABASE_URL debe especificar el nombre de la base de pruebas")

    with psycopg.connect(
        host=url.host or "localhost",
        port=url.port or 5432,
        dbname="postgres",
        user=url.username,
        password=url.password,
        autocommit=True,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,))
            if cursor.fetchone() is None:
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database)))


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    database_url = make_url(TEST_DATABASE_URL)
    _ensure_test_database(database_url)
    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_test_database(test_engine) -> Generator[None, None, None]:
    with test_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    yield


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    with Session(test_engine) as session:
        yield session


@pytest.fixture
def fake_publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture
def client(test_engine, fake_publisher) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_event_publisher] = lambda: fake_publisher
    test_client = TestClient(app)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()


@pytest.fixture
def token_factory():
    def make_token(
        user_id: UUID = TEST_USER_ID,
        email: str | None = "usuario@correo.com",
        expires_in_minutes: int = 60,
        secret: str | None = None,
    ) -> str:
        now = datetime.now(UTC)
        claims: dict[str, str | datetime] = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=expires_in_minutes),
        }
        if email is not None:
            claims["email"] = email
        return jwt.encode(claims, secret or settings.jwt_secret, algorithm="HS256")

    return make_token


@pytest.fixture
def records(db_session: Session):
    def make_center(name: str = "Centro de prueba") -> MedicalCenter:
        center = MedicalCenter(name=name, location="Calle de prueba, Bogotá")
        db_session.add(center)
        db_session.commit()
        return center

    def make_physician(
        center: MedicalCenter,
        specialty: AppointmentType = AppointmentType.GENERAL,
        secondary_center: MedicalCenter | None = None,
    ) -> Physician:
        physician = Physician(
            first_name="Médico",
            last_name="De prueba",
            specialty=specialty,
            primary_med_center_id=center.medical_center_id,
            secondary_med_center_id=(
                secondary_center.medical_center_id if secondary_center is not None else None
            ),
        )
        db_session.add(physician)
        db_session.commit()
        return physician

    def make_appointment(
        physician: Physician,
        center: MedicalCenter,
        appointment_date: date,
        start_time: time,
        user_id: UUID | None = None,
        appointment_type: AppointmentType | None = None,
    ) -> Appointment:
        end_time = (datetime.combine(appointment_date, start_time) + timedelta(minutes=30)).time()
        appointment = Appointment(
            type=appointment_type or physician.specialty,
            date=appointment_date,
            weekday=appointment_date.strftime("%A"),
            start_time=start_time,
            end_time=end_time,
            physician_id=physician.physician_id,
            medical_center_id=center.medical_center_id,
            user_id=user_id,
        )
        db_session.add(appointment)
        db_session.commit()
        return appointment

    return {
        "center": make_center,
        "physician": make_physician,
        "appointment": make_appointment,
    }
