from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.authz import KnownUser, require_known_user
from app.database import get_db
from app.events.publisher import EventPublisher, get_event_publisher
from app.models import AppointmentType
from app.schemas import AppointmentResponse, PaginatedAppointments, RescheduleRequest
from app.services.appointment_service import (
    cancel_appointment,
    list_available,
    list_mine,
    reschedule_appointment,
    schedule_appointment,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get(
    "/available",
    response_model=PaginatedAppointments,
    dependencies=[Depends(require_known_user)],
)
def get_available_appointments(
    appointment_type: AppointmentType | None = Query(default=None, alias="type"),
    medical_center_id: UUID | None = None,
    physician_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1),
    database_session: Session = Depends(get_db),
) -> PaginatedAppointments:
    return list_available(
        database_session=database_session,
        appointment_type=appointment_type,
        medical_center_id=medical_center_id,
        physician_id=physician_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.get("/me", response_model=list[AppointmentResponse])
def get_my_appointments(
    include_past: bool = Query(default=False),
    database_session: Session = Depends(get_db),
    authenticated_user: KnownUser = Depends(require_known_user),
) -> list[AppointmentResponse]:
    return list_mine(
        database_session,
        user_id=authenticated_user.user_id,
        include_past=include_past,
    )


@router.post("/{id}/schedule", response_model=AppointmentResponse)
def post_schedule_appointment(
    id: UUID,
    database_session: Session = Depends(get_db),
    authenticated_user: KnownUser = Depends(require_known_user),
    publisher: EventPublisher = Depends(get_event_publisher),
) -> AppointmentResponse:
    return schedule_appointment(
        database_session=database_session,
        appointment_id=id,
        user_id=authenticated_user.user_id,
        publisher=publisher,
    )


@router.post("/{id}/cancel", response_model=AppointmentResponse)
def post_cancel_appointment(
    id: UUID,
    database_session: Session = Depends(get_db),
    authenticated_user: KnownUser = Depends(require_known_user),
    publisher: EventPublisher = Depends(get_event_publisher),
) -> AppointmentResponse:
    return cancel_appointment(
        database_session=database_session,
        appointment_id=id,
        user_id=authenticated_user.user_id,
        publisher=publisher,
    )


@router.post("/{id}/reschedule", response_model=AppointmentResponse)
def post_reschedule_appointment(
    id: UUID,
    request_body: RescheduleRequest,
    database_session: Session = Depends(get_db),
    authenticated_user: KnownUser = Depends(require_known_user),
    publisher: EventPublisher = Depends(get_event_publisher),
) -> AppointmentResponse:
    return reschedule_appointment(
        database_session=database_session,
        appointment_id=id,
        new_appointment_id=request_body.new_appointment_id,
        user_id=authenticated_user.user_id,
        publisher=publisher,
    )
