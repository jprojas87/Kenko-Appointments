from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, create_tables
from app.errors import DomainError
from app.events.log_publisher import LogPublisher
from app.models import Appointment, MedicalCenter, Physician
from app.services.appointment_service import (
    cancel_appointment,
    reschedule_appointment,
    schedule_appointment,
)
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


def _show_appointments(
    database_session: Session,
    user_id: str,
) -> list[tuple[Appointment, Physician, MedicalCenter]]:
    appointments = _load_demo_appointments(database_session)
    print(f"\nUsuario actual: {user_id}")
    print(f"\nCitas demo compartidas ({len(appointments)} de {DEMO_APPOINTMENT_COUNT}):")
    if not appointments:
        print("  No hay citas demo cargadas. Ejecuta primero: uv run python -m seeds.demo")
        return appointments

    for index, context in enumerate(appointments, start=1):
        _print_appointment(index, context, user_id)

    mine = [context for context in appointments if context[0].user_id == user_id]
    print(f"\nMis citas ({len(mine)}):")
    if not mine:
        print("  No tienes citas agendadas en el conjunto demo.")
    else:
        for index, context in enumerate(mine, start=1):
            _print_appointment(index, context, user_id)
    return appointments


def _select_appointment(
    appointments: list[tuple[Appointment, Physician, MedicalCenter]],
    user_id: str,
    predicate: Callable[[Appointment], bool],
    prompt: str,
) -> tuple[Appointment, Physician, MedicalCenter] | None:
    candidates = [
        (index, context)
        for index, context in enumerate(appointments, start=1)
        if predicate(context[0])
    ]
    if not candidates:
        print("No hay citas que puedas seleccionar para esta acción.")
        return None

    for index, context in candidates:
        _print_appointment(index, context, user_id)

    choice = input(f"{prompt} (número o q para volver): ").strip().lower()
    if choice in {"q", "0"}:
        return None
    for index, context in candidates:
        if choice == str(index):
            return context
    print("Número de cita inválido.")
    return None


def _perform_action(
    action: str,
    database_session: Session,
    appointments: list[tuple[Appointment, Physician, MedicalCenter]],
    user_id: str,
) -> None:
    publisher = LogPublisher()
    try:
        if action == "1":
            selected = _select_appointment(
                appointments,
                user_id,
                lambda appointment: appointment.user_id is None,
                "Número de cita para agendar",
            )
            if selected is None:
                return
            result = schedule_appointment(
                database_session,
                appointment_id=selected[0].appointment_id,
                user_id=user_id,
                email=None,
                publisher=publisher,
            )
            print(f"Cita agendada: {result.date} a las {result.start_time}.")
            return

        if action == "2":
            current = _select_appointment(
                appointments,
                user_id,
                lambda appointment: appointment.user_id == user_id,
                "Número de tu cita actual",
            )
            if current is None:
                return
            destination = _select_appointment(
                appointments,
                user_id,
                lambda appointment: (
                    appointment.user_id is None and appointment.type == current[0].type
                ),
                "Número de la nueva cita (debe ser del mismo tipo)",
            )
            if destination is None:
                return
            result = reschedule_appointment(
                database_session,
                appointment_id=current[0].appointment_id,
                new_appointment_id=destination[0].appointment_id,
                user_id=user_id,
                email=None,
                publisher=publisher,
            )
            print(f"Cita reagendada: {result.date} a las {result.start_time}.")
            return

        if action == "3":
            selected = _select_appointment(
                appointments,
                user_id,
                lambda appointment: appointment.user_id == user_id,
                "Número de cita para cancelar",
            )
            if selected is None:
                return
            result = cancel_appointment(
                database_session,
                appointment_id=selected[0].appointment_id,
                user_id=user_id,
                email=None,
                publisher=publisher,
            )
            print(f"Cita cancelada: {result.date} a las {result.start_time}.")
    except DomainError as error:
        database_session.rollback()
        print(f"No se pudo completar la acción: {error.message}")


def _run_user_session(user_id: str) -> bool:
    while True:
        with SessionLocal() as database_session:
            appointments = _show_appointments(database_session, user_id)

        print("\n¿Qué deseas hacer?")
        print("  1) Agendar una cita")
        print("  2) Reagendar una cita")
        print("  3) Cancelar una cita")
        print("  4) Cambiar de usuario")
        print("  0) Salir")
        action = input("Opción: ").strip().lower()
        if action in {"0", "q", "salir"}:
            return False
        if action == "4":
            return True
        if action not in {"1", "2", "3"}:
            print("Opción inválida.")
            continue

        with SessionLocal() as database_session:
            _perform_action(action, database_session, appointments, user_id)


def main() -> None:
    create_tables()
    print("Kenko Appointments — consola local")
    while True:
        user_id = _choose_user()
        if user_id is None:
            print("Sesión finalizada.")
            return
        if not _run_user_session(user_id):
            print("Sesión finalizada.")
            return


if __name__ == "__main__":
    main()
