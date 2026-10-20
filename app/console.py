from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, create_tables
from app.models import Appointment, MedicalCenter, Physician
from seeds.demo import DEMO_APPOINTMENT_COUNT, demo_appointment_ids


def _choose_user() -> str | None:
    users = settings.configured_demo_user_ids
    print("\nSelecciona el usuario que va a iniciar sesión:")
    for index, user_id in enumerate(users, start=1):
        print(f"  {index}) {user_id}")
    print("  0) Salir")

    while True:
        choice = input("Usuario: ").strip()
        if choice in {"0", "q", "salir"}:
            return None
        if choice in users:
            return choice
        if choice.isdigit() and 1 <= int(choice) <= len(users):
            return users[int(choice) - 1]
        print("Opción inválida; elige el número o el ID de un usuario listado.")


def _load_demo_appointments(
    database_session: Session,
) -> list[tuple[Appointment, Physician, MedicalCenter]]:
    statement = (
        select(Appointment, Physician, MedicalCenter)
        .join(Physician, Physician.physician_id == Appointment.physician_id)
        .join(MedicalCenter, MedicalCenter.medical_center_id == Appointment.medical_center_id)
        .where(Appointment.appointment_id.in_(demo_appointment_ids()))
        .order_by(Appointment.date, Appointment.start_time)
    )
    return [tuple(row) for row in database_session.execute(statement).all()]


def _print_appointment(
    index: int,
    context: tuple[Appointment, Physician, MedicalCenter],
    user_id: str,
) -> None:
    appointment, physician, medical_center = context
    if appointment.user_id == user_id:
        status = "TUYA"
    elif appointment.user_id is None:
        status = "DISPONIBLE"
    else:
        status = "OCUPADA"

    print(
        f"  {index:02}. {appointment.date.isoformat()} "
        f"{appointment.start_time.strftime('%H:%M')} | {appointment.type.value} | "
        f"{physician.first_name} {physician.last_name} | {medical_center.name} | {status} | "
        f"ID: {appointment.appointment_id}"
    )


def _show_appointments(database_session: Session, user_id: str) -> None:
    appointments = _load_demo_appointments(database_session)
    print(f"\nUsuario actual: {user_id}")
    print(f"\nCitas demo compartidas ({len(appointments)} de {DEMO_APPOINTMENT_COUNT}):")
    if not appointments:
        print("  No hay citas demo cargadas. Ejecuta primero: uv run python -m seeds.demo")
        return

    for index, context in enumerate(appointments, start=1):
        _print_appointment(index, context, user_id)

    mine = [context for context in appointments if context[0].user_id == user_id]
    print(f"\nMis citas ({len(mine)}):")
    if not mine:
        print("  No tienes citas agendadas en el conjunto demo.")
    else:
        for index, context in enumerate(mine, start=1):
            _print_appointment(index, context, user_id)


def main() -> None:
    create_tables()
    print("Kenko Appointments — consola local")
    while True:
        user_id = _choose_user()
        if user_id is None:
            print("Sesión finalizada.")
            return

        with SessionLocal() as database_session:
            _show_appointments(database_session, user_id)

        choice = input("\nEnter para elegir otro usuario o 'q' para salir: ").strip().lower()
        if choice == "q":
            print("Sesión finalizada.")
            return


if __name__ == "__main__":
    main()
