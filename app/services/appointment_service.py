from datetime import date
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.errors import BusinessRuleError, ConflictError, NotFoundError
from app.events.envelope import (
    AppointmentContext,
    appointment_cancelled_detail,
    appointment_rescheduled_detail,
    appointment_scheduled_detail,
)
from app.events.publisher import EventPublisher, publish_safely
from app.models import Appointment, AppointmentType, MedicalCenter, Physician
from app.rules import has_minimum_notice, is_future, is_within_max_days_ahead
from app.schemas import (
    AppointmentResponse,
    MedicalCenterSummary,
    PaginatedAppointments,
    PhysicianSummary,
)
from app.services.user_service import require_user


def _appointment_response(
    appointment: Appointment,
    physician: Physician,
    medical_center: MedicalCenter,
) -> AppointmentResponse:
    return AppointmentResponse(
        appointment_id=appointment.appointment_id,
        type=appointment.type,
        date=appointment.date,
        weekday=appointment.weekday,
        start_time=appointment.start_time.strftime("%H:%M"),
        end_time=appointment.end_time.strftime("%H:%M"),
        physician=PhysicianSummary(
            physician_id=physician.physician_id,
            name=f"{physician.first_name} {physician.last_name}",
        ),
        medical_center=MedicalCenterSummary(
            medical_center_id=medical_center.medical_center_id,
            name=medical_center.name,
            location=medical_center.location,
        ),
    )


def list_available(
    database_session: Session,
    appointment_type: AppointmentType | None,
    medical_center_id: UUID | None,
    physician_id: UUID | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
) -> PaginatedAppointments:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise BusinessRuleError("date_from no puede ser posterior a date_to")

    statement = (
        select(Appointment, Physician, MedicalCenter)
        .join(Physician, Physician.physician_id == Appointment.physician_id)
        .join(MedicalCenter, MedicalCenter.medical_center_id == Appointment.medical_center_id)
        .where(Appointment.user_id.is_(None))
    )
    if appointment_type is not None:
        statement = statement.where(Appointment.type == appointment_type)
    if medical_center_id is not None:
        statement = statement.where(Appointment.medical_center_id == medical_center_id)
    if physician_id is not None:
        statement = statement.where(Appointment.physician_id == physician_id)
    if date_from is not None:
        statement = statement.where(Appointment.date >= date_from)
    if date_to is not None:
        statement = statement.where(Appointment.date <= date_to)
    statement = statement.order_by(Appointment.date, Appointment.start_time)

    rows = database_session.execute(statement).all()
    items = [
        _appointment_response(appointment, physician, medical_center)
        for appointment, physician, medical_center in rows
        if is_future(appointment.date, appointment.start_time)
    ]
    total = len(items)
    start = (page - 1) * page_size
    return PaginatedAppointments(
        page=page,
        page_size=page_size,
        total=total,
        items=items[start : start + page_size],
    )


def list_mine(
    database_session: Session,
    user_id: UUID,
    include_past: bool = False,
) -> list[AppointmentResponse]:
    statement = (
        select(Appointment, Physician, MedicalCenter)
        .join(Physician, Physician.physician_id == Appointment.physician_id)
        .join(MedicalCenter, MedicalCenter.medical_center_id == Appointment.medical_center_id)
        .where(Appointment.user_id == user_id)
        .order_by(Appointment.date, Appointment.start_time)
    )
    rows = database_session.execute(statement).all()
    return [
        _appointment_response(appointment, physician, medical_center)
        for appointment, physician, medical_center in rows
        if include_past or is_future(appointment.date, appointment.start_time)
    ]


def _load_appointment_context(
    database_session: Session,
    appointment_id: UUID,
) -> AppointmentContext | None:
    statement = (
        select(Appointment, Physician, MedicalCenter)
        .join(Physician, Physician.physician_id == Appointment.physician_id)
        .join(MedicalCenter, MedicalCenter.medical_center_id == Appointment.medical_center_id)
        .where(Appointment.appointment_id == appointment_id)
    )
    row = database_session.execute(statement).first()
    return tuple(row) if row is not None else None


def schedule_appointment(
    database_session: Session,
    appointment_id: UUID,
    user_id: UUID,
    publisher: EventPublisher,
) -> AppointmentResponse:
    user = require_user(database_session, user_id)
    email = user.email
    first_name = user.first_name
    context = _load_appointment_context(database_session, appointment_id)
    if context is None:
        raise NotFoundError("Cita no encontrada")

    appointment, _physician, _medical_center = context
    if appointment.user_id is not None:
        raise ConflictError("cita no disponible")
    if not is_future(appointment.date, appointment.start_time):
        raise BusinessRuleError("La cita debe ser futura")
    if not is_within_max_days_ahead(appointment.date):
        raise BusinessRuleError("La cita supera el máximo de días de antelación")

    detail = appointment_scheduled_detail(
        context, user_id=user_id, email=email, first_name=first_name
    )
    response = _appointment_response(*context)
    result = database_session.execute(
        update(Appointment)
        .where(
            Appointment.appointment_id == appointment_id,
            Appointment.user_id.is_(None),
        )
        .values(user_id=user_id)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        database_session.rollback()
        exists = database_session.scalar(
            select(Appointment.appointment_id).where(Appointment.appointment_id == appointment_id)
        )
        if exists is None:
            raise NotFoundError("Cita no encontrada")
        raise ConflictError("cita no disponible")

    database_session.commit()
    publish_safely(publisher, "AppointmentScheduled", detail)
    return response


def cancel_appointment(
    database_session: Session,
    appointment_id: UUID,
    user_id: UUID,
    publisher: EventPublisher,
) -> AppointmentResponse:
    user = require_user(database_session, user_id)
    email = user.email
    first_name = user.first_name
    context = _load_appointment_context(database_session, appointment_id)
    if context is None or context[0].user_id != user_id:
        raise NotFoundError("Cita no encontrada")

    appointment = context[0]
    if not has_minimum_notice(appointment.date, appointment.start_time):
        raise BusinessRuleError("La cancelación requiere la anticipación mínima")

    detail = appointment_cancelled_detail(
        context, user_id=user_id, email=email, first_name=first_name
    )
    response = _appointment_response(*context)
    result = database_session.execute(
        update(Appointment)
        .where(
            Appointment.appointment_id == appointment_id,
            Appointment.user_id == user_id,
        )
        .values(user_id=None)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        database_session.rollback()
        raise NotFoundError("Cita no encontrada")

    database_session.commit()
    publish_safely(publisher, "AppointmentCancelled", detail)
    return response


def reschedule_appointment(
    database_session: Session,
    appointment_id: UUID,
    new_appointment_id: UUID,
    user_id: UUID,
    publisher: EventPublisher,
) -> AppointmentResponse:
    user = require_user(database_session, user_id)
    email = user.email
    first_name = user.first_name
    if appointment_id == new_appointment_id:
        raise BusinessRuleError("La nueva cita debe ser diferente a la actual")

    ordered_ids = sorted((appointment_id, new_appointment_id))
    locked_appointments = database_session.scalars(
        select(Appointment)
        .where(Appointment.appointment_id.in_(ordered_ids))
        .order_by(Appointment.appointment_id)
        .with_for_update()
    ).all()
    appointments_by_id = {
        appointment.appointment_id: appointment for appointment in locked_appointments
    }
    previous_appointment = appointments_by_id.get(appointment_id)
    new_appointment = appointments_by_id.get(new_appointment_id)

    if previous_appointment is None or previous_appointment.user_id != user_id:
        raise NotFoundError("Cita no encontrada")
    if new_appointment is None:
        raise NotFoundError("Cita no encontrada")
    if not has_minimum_notice(previous_appointment.date, previous_appointment.start_time):
        raise BusinessRuleError("El reagendamiento requiere la anticipación mínima")
    if new_appointment.user_id is not None:
        raise ConflictError("cita no disponible")
    if new_appointment.type != previous_appointment.type:
        raise BusinessRuleError("La nueva cita debe ser del mismo tipo")
    if not is_future(new_appointment.date, new_appointment.start_time):
        raise BusinessRuleError("La cita debe ser futura")
    if not is_within_max_days_ahead(new_appointment.date):
        raise BusinessRuleError("La cita supera el máximo de días de antelación")

    previous_context = _load_appointment_context(database_session, appointment_id)
    new_context = _load_appointment_context(database_session, new_appointment_id)
    if previous_context is None or new_context is None:
        raise NotFoundError("Cita no encontrada")

    detail = appointment_rescheduled_detail(
        previous_context,
        new_context,
        user_id=user_id,
        email=email,
        first_name=first_name,
    )
    response = _appointment_response(*new_context)
    release_result = database_session.execute(
        update(Appointment)
        .where(
            Appointment.appointment_id == appointment_id,
            Appointment.user_id == user_id,
        )
        .values(user_id=None)
        .execution_options(synchronize_session=False)
    )
    if release_result.rowcount == 0:
        database_session.rollback()
        raise NotFoundError("Cita no encontrada")

    claim_result = database_session.execute(
        update(Appointment)
        .where(
            Appointment.appointment_id == new_appointment_id,
            Appointment.user_id.is_(None),
        )
        .values(user_id=user_id)
        .execution_options(synchronize_session=False)
    )
    if claim_result.rowcount == 0:
        database_session.rollback()
        raise ConflictError("cita no disponible")

    database_session.commit()
    publish_safely(publisher, "AppointmentRescheduled", detail)
    return response
