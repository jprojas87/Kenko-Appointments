import json
from uuid import UUID

import jwt
import pytest
from fastapi.testclient import TestClient
from uuid_utils import uuid7

from app.config import settings
from app.services.profile_ingest import parse_profile_created, upsert_user

TEST_USER_ID = UUID("0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000")


def _profile_event(
    user_id: str = str(TEST_USER_ID),
    email: str = "maria.gomez@example.com",
    first_name: str = "Maria Fernanda",
) -> str:
    return json.dumps(
        {
            "source": "kenko.profile",
            "detail-type": "ProfileCreated",
            "detail": {
                "metadata": {
                    "eventId": str(uuid7()),
                    "eventVersion": "1",
                    "occurredAt": "2026-10-13T20:15:31Z",
                    "correlationId": str(uuid7()),
                },
                "data": {
                    "userId": user_id,
                    "document": {"type": "CC", "number": "1020304050"},
                    "person": {"firstName": first_name, "lastName": "Gomez Rojas"},
                    "contact": {"email": email, "phone": "+573001234567"},
                    "address": {"line": "Cra 15 # 93-60", "city": "Bogota"},
                    "createdAt": "2026-10-13T20:15:31Z",
                },
            },
        }
    )


def test_parse_profile_created_ok() -> None:
    user_id, email, first_name, last_name = parse_profile_created(_profile_event())
    assert user_id == TEST_USER_ID
    assert email == "maria.gomez@example.com"
    assert first_name == "Maria Fernanda"
    assert last_name == "Gomez Rojas"


def test_parse_ignores_other_sources() -> None:
    other = json.dumps({"source": "kenko.other", "detail-type": "X", "detail": {}})
    assert parse_profile_created(other) is None


def test_parse_rejects_bad_email() -> None:
    with pytest.raises(ValueError, match="email"):
        parse_profile_created(_profile_event(email="no-es-email"))


def test_parse_rejects_non_v7_user_id() -> None:
    with pytest.raises(ValueError, match="v7"):
        parse_profile_created(_profile_event(user_id="b6e7cfd2-4f84-4b65-8d63-0ef9ebd76784"))


def test_parse_rejects_missing_first_name() -> None:
    with pytest.raises(ValueError, match="firstName"):
        parse_profile_created(_profile_event(first_name="   "))


def test_upsert_is_idempotent(db_session, records) -> None:
    first = upsert_user(db_session, TEST_USER_ID, "a@correo.com", "Ana", "Perez")
    second = upsert_user(db_session, TEST_USER_ID, "a@correo.com", "Ana", "Perez")
    assert first.user_id == second.user_id == TEST_USER_ID
    assert first.first_name == "Ana"
    assert db_session.query(type(first)).count() == 1
    third = upsert_user(db_session, TEST_USER_ID, "b@correo.com", "Rupaul", "Charles")
    assert third.email == "b@correo.com"
    assert third.first_name == "Rupaul"
    assert db_session.query(type(first)).count() == 1


def test_jwt_rejects_wrong_issuer_or_audience(client: TestClient, token_factory) -> None:
    path = "/api/v1/appointments/available"
    bad_iss = client.get(
        path,
        headers={"Authorization": f"Bearer {token_factory(issuer='impostor')}"},
    )
    bad_aud = client.get(
        path,
        headers={"Authorization": f"Bearer {token_factory(audience='otra-api')}"},
    )
    assert bad_iss.status_code == bad_aud.status_code == 401


def test_jwt_rejects_opaque_refresh_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/appointments/available",
        headers={"Authorization": "Bearer token-opaco-de-32-bytes-xyz"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_jwt_rejects_non_v7_sub(client: TestClient, token_factory) -> None:
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    v4_token = jwt.encode(
        {
            "sub": "b6e7cfd2-4f84-4b65-8d63-0ef9ebd76784",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": now + timedelta(minutes=15),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    response = client.get(
        "/api/v1/appointments/available",
        headers={"Authorization": f"Bearer {v4_token}"},
    )
    assert response.status_code == 401


def test_jwt_tolerates_small_clock_skew(client: TestClient, records) -> None:
    """Los relojes de Auth y Appointments pueden diferir: iat levemente futuro OK."""
    from datetime import UTC, datetime, timedelta

    records["user"]()
    now = datetime.now(UTC)
    skewed = jwt.encode(
        {
            "sub": str(TEST_USER_ID),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now + timedelta(seconds=60),
            "exp": now + timedelta(minutes=15),
            "jti": "01a173d4-5671-74e8-bcb9-c006ac1351b9",
            "sid": "01a173d4-5671-74e8-bcb9-c006ac1351c0",
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    response = client.get(
        "/api/v1/appointments/available",
        headers={"Authorization": f"Bearer {skewed}"},
    )
    assert response.status_code == 200
