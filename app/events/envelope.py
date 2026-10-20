from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.logging_config import get_correlation_id
from app.models import Appointment, MedicalCenter, Physician

EVENT_SOURCE = "kenko.appointments"
AppointmentContext = tuple[Appointment, Physician, MedicalCenter]


def _utc_timestamp(value: datetime | None = None) -> str:
    timestamp = value or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _correlation_id(value: str | None = None) -> str:
    return value or get_correlation_id() or str(uuid4())


def _metadata(
    occurred_at: str,
    correlation_id: str | None,
    event_id: UUID | None,
) -> dict[str, str]:
    return {
        "eventId": str(event_id or uuid4()),
        "eventVersion": "1",
        "occurredAt": occurred_at,
        "correlationId": _correlation_id(correlation_id),
    }


def _appointment_data(context: AppointmentContext) -> dict[str, object]:
    appointment, physician, medical_center = context
    return {
        "appointmentId": str(appointment.appointment_id),
        "type": appointment.type.value,
        "date": appointment.date.isoformat(),
        "weekday": appointment.weekday,
        "startTime": appointment.start_time.strftime("%H:%M"),
        "endTime": appointment.end_time.strftime("%H:%M"),
        "physician": {
            "physicianId": str(physician.physician_id),
            "name": f"{physician.first_name} {physician.last_name}",
        },
        "medicalCenter": {
            "medicalCenterId": str(medical_center.medical_center_id),
            "name": medical_center.name,
            "location": medical_center.location,
        },
    }


def appointment_scheduled_detail(
    context: AppointmentContext,
    user_id: str,
    email: str | None,
    occurred_at: datetime | None = None,
    correlation_id: str | None = None,
    event_id: UUID | None = None,
) -> dict[str, object]:
    timestamp = _utc_timestamp(occurred_at)
    return {
        "metadata": _metadata(timestamp, correlation_id, event_id),
        "data": {
            "userId": str(user_id),
            "email": email,
            "scheduledAt": timestamp,
            "appointment": _appointment_data(context),
        },
    }


def appointment_rescheduled_detail(
    previous_context: AppointmentContext,
    new_context: AppointmentContext,
    user_id: str,
    email: str | None,
    occurred_at: datetime | None = None,
    correlation_id: str | None = None,
    event_id: UUID | None = None,
) -> dict[str, object]:
    timestamp = _utc_timestamp(occurred_at)
    return {
        "metadata": _metadata(timestamp, correlation_id, event_id),
        "data": {
            "userId": str(user_id),
            "email": email,
            "rescheduledAt": timestamp,
            "previousAppointment": _appointment_data(previous_context),
            "appointment": _appointment_data(new_context),
        },
    }


def appointment_cancelled_detail(
    context: AppointmentContext,
    user_id: str,
    email: str | None,
    occurred_at: datetime | None = None,
    correlation_id: str | None = None,
    event_id: UUID | None = None,
) -> dict[str, object]:
    timestamp = _utc_timestamp(occurred_at)
    return {
        "metadata": _metadata(timestamp, correlation_id, event_id),
        "data": {
            "userId": str(user_id),
            "email": email,
            "cancelledAt": timestamp,
            "appointment": _appointment_data(context),
        },
    }
