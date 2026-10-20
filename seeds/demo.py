from datetime import datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from app.database import SessionLocal
from app.models import Appointment, MedicalCenter, Physician
from seeds.run import MEDICAL_CENTERS, PHYSICIANS, insert_if_missing, seed_uuid

BOGOTA = ZoneInfo("America/Bogota")
DEMO_APPOINTMENT_COUNT = 20
DAILY_START_TIMES = (time(9, 0), time(10, 0), time(14, 0), time(15, 0))


def demo_appointment_ids() -> tuple[UUID, ...]:
    return tuple(
        seed_uuid("demo_appointment", f"slot:{index:02}") for index in range(DEMO_APPOINTMENT_COUNT)
    )


def build_demo_appointment_rows(now: datetime | None = None) -> list[dict[str, object]]:
    current_time = now or datetime.now(BOGOTA)
    center_ids = {
        key: seed_uuid("medical_center", key) for key, _name, _location in MEDICAL_CENTERS
    }
    physician_ids = {row[0]: seed_uuid("physician", row[0]) for row in PHYSICIANS}
    appointment_ids = demo_appointment_ids()
    rows: list[dict[str, object]] = []
    day = current_time.date()

    while len(rows) < DEMO_APPOINTMENT_COUNT:
        day += timedelta(days=1)
        if day.weekday() >= 5:
            continue

        for start_time in DAILY_START_TIMES:
            index = len(rows)
            physician_row = PHYSICIANS[index % len(PHYSICIANS)]
            physician_key, _first, _last, specialty, center_key, _secondary = physician_row
            rows.append(
                {
                    "appointment_id": appointment_ids[index],
                    "type": specialty,
                    "date": day,
                    "weekday": day.strftime("%A"),
                    "start_time": start_time,
                    "end_time": (datetime.combine(day, start_time) + timedelta(minutes=30)).time(),
                    "physician_id": physician_ids[physician_key],
                    "medical_center_id": center_ids[center_key],
                    "user_id": None,
                }
            )
            if len(rows) == DEMO_APPOINTMENT_COUNT:
                break

    return rows


def _seed_demo_appointments(session: Session, rows: list[dict[str, object]]) -> None:
    statement = insert(Appointment.__table__).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[Appointment.appointment_id],
        set_={
            "type": statement.excluded.type,
            "date": statement.excluded.date,
            "weekday": statement.excluded.weekday,
            "start_time": statement.excluded.start_time,
            "end_time": statement.excluded.end_time,
            "physician_id": statement.excluded.physician_id,
            "medical_center_id": statement.excluded.medical_center_id,
        },
        where=Appointment.user_id.is_(None),
    )
    session.execute(statement)


def run_demo_seed(session_factory: sessionmaker[Session] = SessionLocal) -> None:
    center_ids = {
        key: seed_uuid("medical_center", key) for key, _name, _location in MEDICAL_CENTERS
    }
    physician_ids = {row[0]: seed_uuid("physician", row[0]) for row in PHYSICIANS}
    center_rows = [
        {"medical_center_id": center_ids[key], "name": name, "location": location}
        for key, name, location in MEDICAL_CENTERS
    ]
    physician_rows = [
        {
            "physician_id": physician_ids[key],
            "first_name": first_name,
            "last_name": last_name,
            "specialty": specialty,
            "primary_med_center_id": center_ids[primary_key],
            "secondary_med_center_id": center_ids[secondary_key] if secondary_key else None,
        }
        for key, first_name, last_name, specialty, primary_key, secondary_key in PHYSICIANS
    ]

    with session_factory.begin() as session:
        insert_if_missing(session, MedicalCenter.__table__, center_rows, "medical_center_id")
        insert_if_missing(session, Physician.__table__, physician_rows, "physician_id")
        _seed_demo_appointments(session, build_demo_appointment_rows())

    print(f"Seed demo listo: {DEMO_APPOINTMENT_COUNT} citas compartidas.")


if __name__ == "__main__":
    run_demo_seed()
