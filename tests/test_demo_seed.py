from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Appointment
from seeds.demo import DEMO_APPOINTMENT_COUNT, run_demo_seed
from seeds.run import seed_uuid

BOGOTA = ZoneInfo("America/Bogota")


def test_demo_seed_creates_twenty_shared_slots_and_is_idempotent(
    test_engine,
) -> None:
    test_session_factory = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    run_demo_seed(test_session_factory)

    with Session(test_engine) as session:
        demo_appointment_ids = [
            seed_uuid("demo_appointment", f"slot:{index:02}")
            for index in range(DEMO_APPOINTMENT_COUNT)
        ]
        appointments = session.scalars(
            select(Appointment).where(Appointment.appointment_id.in_(demo_appointment_ids))
        ).all()

    assert len(appointments) == DEMO_APPOINTMENT_COUNT
    assert all(appointment.user_id is None for appointment in appointments)
    assert all(appointment.date > datetime.now(BOGOTA).date() for appointment in appointments)

    run_demo_seed(test_session_factory)

    with Session(test_engine) as session:
        assert (
            len(
                session.scalars(
                    select(Appointment).where(Appointment.appointment_id.in_(demo_appointment_ids))
                ).all()
            )
            == DEMO_APPOINTMENT_COUNT
        )


def test_demo_seed_does_not_clear_a_booked_slot(test_engine) -> None:
    test_session_factory = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    booked_id = seed_uuid("demo_appointment", "slot:00")

    run_demo_seed(test_session_factory)
    with Session(test_engine) as session:
        appointment = session.get(Appointment, booked_id)
        assert appointment is not None
        appointment.user_id = "USR01"
        session.commit()

    run_demo_seed(test_session_factory)

    with Session(test_engine) as session:
        appointment = session.get(Appointment, booked_id)
        assert appointment is not None
        assert appointment.user_id == "USR01"


def test_demo_appointments_are_within_the_scheduling_horizon() -> None:
    from seeds.demo import build_demo_appointment_rows

    today = datetime.now(BOGOTA).date()
    rows = build_demo_appointment_rows()

    assert len(rows) == DEMO_APPOINTMENT_COUNT
    assert all(today < row["date"] <= today + timedelta(days=90) for row in rows)
