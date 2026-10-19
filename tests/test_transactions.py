from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Appointment, AppointmentType

TEST_USER_ID = UUID("0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000")
OTHER_USER_ID = UUID("0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8001")


BOGOTA = ZoneInfo("America/Bogota")


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def future_date(days: int) -> date:
    return datetime.now(BOGOTA).date() + timedelta(days=days)


def future_slot(hours: int) -> tuple[date, time]:
    slot = (datetime.now(BOGOTA) + timedelta(hours=hours)).replace(second=0, microsecond=0)
    return slot.date(), slot.time().replace(tzinfo=None)


@pytest.mark.parametrize("round_number", range(3))
def test_only_one_concurrent_schedule_succeeds(
    round_number,
    client: TestClient,
    token_factory,
    records,
    fake_publisher,
) -> None:
    center = records["center"](f"Centro concurrencia {round_number}")
    physician = records["physician"](center)
    appointment = records["appointment"](
        physician,
        center,
        future_date(3),
        time(9, 0),
    )
    token = token_factory()
    path = f"/api/v1/appointments/{appointment.appointment_id}/schedule"

    def schedule_once() -> int:
        return client.post(path, headers=authorization(token)).status_code

    with ThreadPoolExecutor(max_workers=10) as executor:
        statuses = list(executor.map(lambda _index: schedule_once(), range(10)))

    assert statuses.count(200) == 1
    assert statuses.count(409) == 9
    assert len(fake_publisher.events) == 1
    assert fake_publisher.events[-1]["detail-type"] == "AppointmentScheduled"


def test_reschedule_is_atomic_and_publishes_once(
    client: TestClient,
    token_factory,
    records,
    db_session: Session,
    fake_publisher,
) -> None:
    center = records["center"]("Centro reagendamiento")
    physician = records["physician"](center)
    previous = records["appointment"](
        physician,
        center,
        future_date(3),
        time(9, 0),
        user_id=TEST_USER_ID,
    )
    busy = records["appointment"](
        physician,
        center,
        future_date(4),
        time(9, 0),
        user_id=OTHER_USER_ID,
    )
    available = records["appointment"](
        physician,
        center,
        future_date(5),
        time(9, 0),
    )
    token = token_factory()
    path = f"/api/v1/appointments/{previous.appointment_id}/reschedule"

    conflict = client.post(
        path,
        headers=authorization(token),
        json={"newAppointmentId": str(busy.appointment_id)},
    )
    assert conflict.status_code == 409
    assert fake_publisher.events == []
    db_session.expire_all()
    assert db_session.get(Appointment, previous.appointment_id).user_id == TEST_USER_ID

    success = client.post(
        path,
        headers=authorization(token),
        json={"newAppointmentId": str(available.appointment_id)},
    )
    assert success.status_code == 200
    assert success.json()["appointmentId"] == str(available.appointment_id)
    db_session.expire_all()
    assert db_session.get(Appointment, previous.appointment_id).user_id is None
    assert db_session.get(Appointment, available.appointment_id).user_id == TEST_USER_ID
    assert len(fake_publisher.events) == 1
    event = fake_publisher.events[0]
    assert event["detail-type"] == "AppointmentRescheduled"
    assert event["detail"]["data"]["previousAppointment"]["appointmentId"] == str(
        previous.appointment_id
    )
    assert event["detail"]["data"]["appointment"]["appointmentId"] == str(available.appointment_id)


def test_cancel_own_appointment_publishes_once_and_returns_to_pool(
    client: TestClient,
    token_factory,
    records,
    db_session: Session,
    fake_publisher,
) -> None:
    center = records["center"]("Centro cancelación")
    physician = records["physician"](center)
    appointment = records["appointment"](
        physician,
        center,
        future_date(3),
        time(9, 0),
        user_id=TEST_USER_ID,
    )
    response = client.post(
        f"/api/v1/appointments/{appointment.appointment_id}/cancel",
        headers=authorization(token_factory()),
    )

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(Appointment, appointment.appointment_id).user_id is None
    assert len(fake_publisher.events) == 1
    event = fake_publisher.events[0]
    assert event["detail-type"] == "AppointmentCancelled"
    assert event["detail"]["data"]["userId"] == str(TEST_USER_ID)
    assert event["detail"]["data"]["email"] == "usuario@correo.com"
    assert event["detail"]["data"]["appointment"]["appointmentId"] == str(
        appointment.appointment_id
    )


def test_foreign_appointments_are_hidden_on_cancel_and_reschedule(
    client: TestClient,
    token_factory,
    records,
    fake_publisher,
) -> None:
    center = records["center"]("Centro cita ajena")
    physician = records["physician"](center)
    foreign = records["appointment"](
        physician,
        center,
        future_date(3),
        time(9, 0),
        user_id=OTHER_USER_ID,
    )
    destination = records["appointment"](
        physician,
        center,
        future_date(4),
        time(9, 0),
    )
    headers = authorization(token_factory())

    cancel = client.post(
        f"/api/v1/appointments/{foreign.appointment_id}/cancel",
        headers=headers,
    )
    reschedule = client.post(
        f"/api/v1/appointments/{foreign.appointment_id}/reschedule",
        headers=headers,
        json={"newAppointmentId": str(destination.appointment_id)},
    )

    assert cancel.status_code == reschedule.status_code == 404
    assert fake_publisher.events == []


def test_past_and_beyond_horizon_scheduling_are_rejected(
    client: TestClient,
    token_factory,
    records,
    fake_publisher,
) -> None:
    center = records["center"]("Centro reglas agenda")
    physician = records["physician"](center)
    past = records["appointment"](
        physician,
        center,
        future_date(-1),
        time(9, 0),
    )
    too_far = records["appointment"](
        physician,
        center,
        future_date(settings.max_days_ahead_to_schedule + 1),
        datetime.min.time().replace(hour=9),
    )
    headers = authorization(token_factory())

    past_response = client.post(
        f"/api/v1/appointments/{past.appointment_id}/schedule",
        headers=headers,
    )
    far_response = client.post(
        f"/api/v1/appointments/{too_far.appointment_id}/schedule",
        headers=headers,
    )

    assert past_response.status_code == far_response.status_code == 422
    assert fake_publisher.events == []


def test_minimum_notice_and_reschedule_type_are_enforced(
    client: TestClient,
    token_factory,
    records,
    db_session: Session,
    fake_publisher,
) -> None:
    center = records["center"]("Centro anticipación")
    general = records["physician"](center, AppointmentType.GENERAL)
    dental = records["physician"](center, AppointmentType.ODONTOLOGIA)
    near_date, near_time = future_slot(8)
    near = records["appointment"](
        general,
        center,
        near_date,
        near_time,
        user_id=TEST_USER_ID,
    )
    future = records["appointment"](general, center, future_date(3), time(9, 0))
    current_for_type_check = records["appointment"](
        general,
        center,
        future_date(4),
        time(9, 0),
        user_id=TEST_USER_ID,
    )
    wrong_type = records["appointment"](
        dental,
        center,
        future_date(5),
        time(9, 0),
    )
    headers = authorization(token_factory())

    cancel = client.post(
        f"/api/v1/appointments/{near.appointment_id}/cancel",
        headers=headers,
    )
    reschedule = client.post(
        f"/api/v1/appointments/{near.appointment_id}/reschedule",
        headers=headers,
        json={"newAppointmentId": str(future.appointment_id)},
    )
    wrong_type_response = client.post(
        f"/api/v1/appointments/{current_for_type_check.appointment_id}/reschedule",
        headers=headers,
        json={"newAppointmentId": str(wrong_type.appointment_id)},
    )

    assert cancel.status_code == reschedule.status_code == wrong_type_response.status_code == 422
    assert fake_publisher.events == []
    db_session.expire_all()
    assert db_session.get(Appointment, near.appointment_id).user_id == TEST_USER_ID
    assert db_session.get(Appointment, future.appointment_id).user_id is None
