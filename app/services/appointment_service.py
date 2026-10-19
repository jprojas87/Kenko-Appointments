from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import BusinessRuleError
from app.models import Appointment, AppointmentType, MedicalCenter, Physician
from app.rules import is_future
from app.schemas import (
    AppointmentResponse,
    MedicalCenterSummary,
    PaginatedAppointments,
    PhysicianSummary,
)


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
