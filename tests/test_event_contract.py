import json
import logging
import re
from datetime import date, datetime, time, timedelta
from uuid import UUID

import boto3
import pytest
from botocore.stub import Stubber
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.events.eventbridge_publisher import EventBridgePublisher
from app.events.publisher import get_event_publisher
from app.main import app
from app.models import Appointment, AppointmentType

TEST_USER_ID = "0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000"
CORRELATION_ID = "9f6c9f73-9200-4e60-a1b6-d9498f6c4819"


def _headers(token: str, correlation_id: str = CORRELATION_ID) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Correlation-Id": correlation_id,
    }


def _assert_appointment_contract(appointment: dict[str, object]) -> None:
    assert set(appointment) == {
        "appointmentId",
        "type",
        "date",
        "weekday",
        "startTime",
        "endTime",
        "physician",
        "medicalCenter",
    }
    UUID(appointment["appointmentId"])
    assert appointment["type"] in {item.value for item in AppointmentType}
    parsed_date = date.fromisoformat(appointment["date"])
    assert appointment["weekday"] == parsed_date.strftime("%A")
    assert re.fullmatch(r"\d{2}:\d{2}", appointment["startTime"])
    assert re.fullmatch(r"\d{2}:\d{2}", appointment["endTime"])
    physician = appointment["physician"]
    assert set(physician) == {"physicianId", "name"}
    UUID(physician["physicianId"])
    assert physician["name"]
    medical_center = appointment["medicalCenter"]
    assert set(medical_center) == {"medicalCenterId", "name", "location"}
    UUID(medical_center["medicalCenterId"])


def _assert_timestamp(value: str) -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.utcoffset() == timedelta(0)


def _assert_event_contract(
    event: dict[str, object],
    detail_type: str,
    timestamp_key: str,
    email: str | None,
    correlation_id: str = CORRELATION_ID,
) -> None:
    assert set(event) == {"source", "detail-type", "detail"}
    assert event["source"] == "kenko.appointments"
    assert event["detail-type"] == detail_type
    detail = event["detail"]
    assert set(detail) == {"metadata", "data"}
    metadata = detail["metadata"]
    assert set(metadata) == {"eventId", "eventVersion", "occurredAt", "correlationId"}
    assert UUID(metadata["eventId"]).version == 4
    assert metadata["eventVersion"] == "1"
    _assert_timestamp(metadata["occurredAt"])
    assert metadata["correlationId"] == correlation_id
    data = detail["data"]
    assert data["userId"] == str(TEST_USER_ID)
    UUID(data["userId"])
    assert "email" in data and data["email"] == email
    assert data[timestamp_key] == metadata["occurredAt"]
    _assert_timestamp(data[timestamp_key])
    if detail_type == "AppointmentRescheduled":
        assert set(data) == {
            "userId",
            "email",
            "rescheduledAt",
            "previousAppointment",
            "appointment",
        }
        _assert_appointment_contract(data["previousAppointment"])
        _assert_appointment_contract(data["appointment"])
    else:
        assert set(data) == {"userId", "email", timestamp_key, "appointment"}
        _assert_appointment_contract(data["appointment"])
    assert "patientId" not in json.dumps(event)


def test_scheduled_event_matches_contract(
    client: TestClient,
    token_factory,
    records,
    fake_publisher,
) -> None:
    center = records["center"]("Sede evento agendado")
    physician = records["physician"](center, AppointmentType.GENERAL)
    appointment = records["appointment"](
        physician,
        center,
        date.today() + timedelta(days=3),
        time(9, 0),
    )

    response = client.post(
        f"/api/v1/appointments/{appointment.appointment_id}/schedule",
        headers=_headers(token_factory()),
    )

    assert response.status_code == 200
    assert len(fake_publisher.events) == 1
    _assert_event_contract(
        fake_publisher.events[0],
        "AppointmentScheduled",
        "scheduledAt",
        "usuario@correo.com",
    )


def test_cancelled_event_matches_contract(
    client: TestClient,
    token_factory,
    records,
    fake_publisher,
) -> None:
    center = records["center"]("Sede evento cancelado")
    physician = records["physician"](center)
    appointment = records["appointment"](
        physician,
        center,
        date.today() + timedelta(days=3),
        time(9, 0),
        user_id=TEST_USER_ID,
    )

    response = client.post(
        f"/api/v1/appointments/{appointment.appointment_id}/cancel",
        headers=_headers(token_factory()),
    )

    assert response.status_code == 200
    assert len(fake_publisher.events) == 1
    _assert_event_contract(
        fake_publisher.events[0],
        "AppointmentCancelled",
        "cancelledAt",
        "usuario@correo.com",
    )


def test_rescheduled_event_matches_contract(
    client: TestClient,
    token_factory,
    records,
    fake_publisher,
) -> None:
    center = records["center"]("Sede evento reagendado")
    physician = records["physician"](center, AppointmentType.ODONTOLOGIA)
    previous = records["appointment"](
        physician,
        center,
        date.today() + timedelta(days=3),
        time(9, 0),
        user_id=TEST_USER_ID,
    )
    new_appointment = records["appointment"](
        physician,
        center,
        date.today() + timedelta(days=4),
        time(9, 0),
    )

    response = client.post(
        f"/api/v1/appointments/{previous.appointment_id}/reschedule",
        headers=_headers(token_factory()),
        json={"newAppointmentId": str(new_appointment.appointment_id)},
    )

    assert response.status_code == 200
    assert len(fake_publisher.events) == 1
    _assert_event_contract(
        fake_publisher.events[0],
        "AppointmentRescheduled",
        "rescheduledAt",
        "usuario@correo.com",
    )


def test_missing_email_is_null_and_warning_is_recorded(
    client: TestClient,
    token_factory,
    records,
    fake_publisher,
    caplog,
) -> None:
    center = records["center"]("Sede evento sin correo")
    physician = records["physician"](center)
    appointment = records["appointment"](
        physician,
        center,
        date.today() + timedelta(days=3),
        time(9, 0),
    )

    with caplog.at_level(logging.WARNING, logger="app.security"):
        response = client.post(
            f"/api/v1/appointments/{appointment.appointment_id}/schedule",
            headers=_headers(token_factory(email=None)),
        )

    assert response.status_code == 200
    _assert_event_contract(
        fake_publisher.events[0],
        "AppointmentScheduled",
        "scheduledAt",
        None,
    )
    assert "no incluye el claim email" in caplog.text


def test_publish_failure_does_not_undo_confirmed_schedule(
    client: TestClient,
    token_factory,
    records,
    db_session: Session,
    caplog,
) -> None:
    center = records["center"]("Sede publicador caído")
    physician = records["physician"](center)
    appointment = records["appointment"](
        physician,
        center,
        date.today() + timedelta(days=3),
        time(9, 0),
    )

    class FailingPublisher:
        attempts = 0

        def publish(self, detail_type, detail):
            self.attempts += 1
            raise RuntimeError("EventBridge no disponible")

    failing_publisher = FailingPublisher()
    app.dependency_overrides[get_event_publisher] = lambda: failing_publisher
    token = token_factory()

    with caplog.at_level(logging.ERROR, logger="app.events.publisher"):
        response = client.post(
            f"/api/v1/appointments/{appointment.appointment_id}/schedule",
            headers=_headers(token),
        )

    assert response.status_code == 200
    assert failing_publisher.attempts == 3
    db_session.expire_all()
    assert db_session.get(Appointment, appointment.appointment_id).user_id == TEST_USER_ID
    assert "correlationId=" in caplog.text
    assert "eventId=" in caplog.text
    assert f"userId={TEST_USER_ID}" in caplog.text


def test_eventbridge_put_events_parameters_and_failed_entry_handling() -> None:
    client = boto3.client(
        "events",
        region_name=settings.aws_region,
        aws_access_key_id="test-access-key",
        aws_secret_access_key="test-secret-key",
    )
    detail = {
        "metadata": {"eventId": "0192b3e0-5f11-7a22-9b33-4c5d6e7f8091"},
        "data": {"userId": str(TEST_USER_ID), "email": "usuario@correo.com"},
    }
    expected_entry = {
        "Source": "kenko.appointments",
        "DetailType": "AppointmentScheduled",
        "Detail": json.dumps(detail, ensure_ascii=False, separators=(",", ":")),
        "EventBusName": settings.event_bus_name,
    }
    publisher = EventBridgePublisher(client=client)

    with Stubber(client) as stubber:
        stubber.add_response(
            "put_events",
            {"FailedEntryCount": 0, "Entries": [{"EventId": "eventbridge-event-id"}]},
            {"Entries": [expected_entry]},
        )
        publisher.publish("AppointmentScheduled", detail)
        stubber.assert_no_pending_responses()

    with Stubber(client) as stubber:
        stubber.add_response(
            "put_events",
            {
                "FailedEntryCount": 1,
                "Entries": [{"ErrorCode": "InternalFailure", "ErrorMessage": "fallo"}],
            },
            {"Entries": [expected_entry]},
        )
        with pytest.raises(RuntimeError, match="EventBridge no publicó"):
            publisher.publish("AppointmentScheduled", detail)
