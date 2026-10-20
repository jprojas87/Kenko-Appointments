from datetime import date, time, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.database import migrate_user_id_column
from app.models import Appointment, AppointmentType, MedicalCenter, Physician

LEGACY_USER_ID = "0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000"


def test_user_id_migration_preserves_existing_uuid_values(
    test_engine: Engine,
    records,
) -> None:
    center: MedicalCenter = records["center"]("Centro migración")
    physician: Physician = records["physician"](center, AppointmentType.GENERAL)
    appointment: Appointment = records["appointment"](
        physician,
        center,
        date.today() + timedelta(days=3),
        time(9, 0),
        user_id=LEGACY_USER_ID,
    )

    with test_engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE appointments ALTER COLUMN user_id TYPE UUID USING user_id::uuid"
        )

    migrate_user_id_column(test_engine)

    with test_engine.connect() as connection:
        data_type = connection.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = 'appointments' AND column_name = 'user_id'"
            )
        ).scalar_one()
        migrated_user_id = connection.execute(
            text("SELECT user_id FROM appointments WHERE appointment_id = :appointment_id"),
            {"appointment_id": appointment.appointment_id},
        ).scalar_one()

    assert data_type == "text"
    assert migrated_user_id == LEGACY_USER_ID
