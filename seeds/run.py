from datetime import date, datetime, time, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.schema import Table

from app.database import SessionLocal
from app.models import Appointment, AppointmentType, MedicalCenter, Physician

BOGOTA = ZoneInfo("America/Bogota")
BATCH_SIZE = 500

MEDICAL_CENTERS = (
    ("bogota_norte", "Centro Médico Norte", "Calle 100 # 15-20, Bogotá"),
    ("bogota_sur", "Centro Médico Sur", "Carrera 30 # 18-45, Bogotá"),
    ("medellin", "Centro Médico Medellín", "Carrera 43A # 1-50, Medellín"),
    ("cali", "Centro Médico Cali", "Avenida 6N # 25-30, Cali"),
    ("barranquilla", "Centro Médico Barranquilla", "Calle 84 # 52-30, Barranquilla"),
)

PHYSICIANS = (
    ("lucia_gomez", "Lucía", "Gómez", AppointmentType.GENERAL, "bogota_norte", "bogota_sur"),
    ("santiago_rojas", "Santiago", "Rojas", AppointmentType.GENERAL, "medellin", None),
    ("camila_torres", "Camila", "Torres", AppointmentType.GENERAL, "cali", "medellin"),
    (
        "andres_martinez",
        "Andrés",
        "Martínez",
        AppointmentType.GENERAL,
        "barranquilla",
        None,
    ),
    (
        "laura_restrepo",
        "Laura",
        "Restrepo",
        AppointmentType.ODONTOLOGIA,
        "bogota_norte",
        "medellin",
    ),
    ("mateo_vargas", "Mateo", "Vargas", AppointmentType.ODONTOLOGIA, "bogota_sur", None),
    (
        "juliana_mejia",
        "Juliana",
        "Mejía",
        AppointmentType.ODONTOLOGIA,
        "cali",
        "barranquilla",
    ),
    (
        "natalia_cardona",
        "Natalia",
        "Cardona",
        AppointmentType.PSICOLOGIA,
        "medellin",
        "bogota_norte",
    ),
    ("felipe_ospina", "Felipe", "Ospina", AppointmentType.PSICOLOGIA, "cali", None),
    (
        "sara_pineda",
        "Sara",
        "Pineda",
        AppointmentType.PSICOLOGIA,
        "barranquilla",
        "bogota_sur",
    ),
)


def seed_uuid(entity: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"kenko-appointments:{entity}:{key}")


def insert_if_missing(
    session: Session, table: Table, records: list[dict[str, object]], key_column: str
) -> None:
    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start : start + BATCH_SIZE]
        statement = (
            insert(table).values(batch).on_conflict_do_nothing(index_elements=[table.c[key_column]])
        )
        session.execute(statement)


def available_slots(day: date, now: datetime) -> list[tuple[time, time]]:
    slots: list[tuple[time, time]] = []
    for first_hour, last_hour in ((8, 12), (14, 17)):
        period_start = datetime.combine(day, time(first_hour), tzinfo=BOGOTA)
        period_end = datetime.combine(day, time(last_hour), tzinfo=BOGOTA)
        while period_start + timedelta(minutes=30) <= period_end:
            period_end_time = period_start + timedelta(minutes=30)
            if period_start > now:
                slots.append((period_start.time(), period_end_time.time()))
            period_start = period_end_time
    return slots


def build_appointment_rows(
    now: datetime,
    center_ids: dict[str, UUID],
    physician_ids: dict[str, UUID],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    first_day = now.date()

    for key, _first_name, _last_name, specialty, primary_key, secondary_key in PHYSICIANS:
        physician_id = physician_ids[key]
        for day_offset in range(60):
            day = first_day + timedelta(days=day_offset)
            if day.weekday() >= 5:
                continue

            center_key = primary_key
            if secondary_key is not None and day.isocalendar().week % 2 == 0:
                center_key = secondary_key

            for start_time, end_time in available_slots(day, now):
                rows.append(
                    {
                        "appointment_id": seed_uuid(
                            "appointment", f"{key}:{day.isoformat()}:{start_time.isoformat()}"
                        ),
                        "type": specialty,
                        "date": day,
                        "weekday": day.strftime("%A"),
                        "start_time": start_time,
                        "end_time": end_time,
                        "physician_id": physician_id,
                        "medical_center_id": center_ids[center_key],
                        "user_id": None,
                    }
                )

    return rows


def run_seed() -> None:
    now = datetime.now(BOGOTA)
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
    appointment_rows = build_appointment_rows(now, center_ids, physician_ids)

    with SessionLocal.begin() as session:
        insert_if_missing(session, MedicalCenter.__table__, center_rows, "medical_center_id")
        insert_if_missing(session, Physician.__table__, physician_rows, "physician_id")
        insert_if_missing(session, Appointment.__table__, appointment_rows, "appointment_id")

        counts = {
            "medical_centers": session.scalar(select(func.count()).select_from(MedicalCenter)),
            "physicians": session.scalar(select(func.count()).select_from(Physician)),
            "appointments": session.scalar(select(func.count()).select_from(Appointment)),
        }

    print(
        "Seed listo: "
        f"{counts['medical_centers']} centros, "
        f"{counts['physicians']} médicos y "
        f"{counts['appointments']} citas en total."
    )


if __name__ == "__main__":
    run_seed()
