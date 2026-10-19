from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import settings

BOGOTA = ZoneInfo("America/Bogota")


def _local_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(BOGOTA)
    if now.tzinfo is None:
        return now.replace(tzinfo=BOGOTA)
    return now.astimezone(BOGOTA)


def _appointment_datetime(appointment_date: date, start_time: time) -> datetime:
    local_time = start_time.replace(tzinfo=None)
    return datetime.combine(appointment_date, local_time, tzinfo=BOGOTA)


def is_future(
    appointment_date: date,
    start_time: time,
    now: datetime | None = None,
) -> bool:
    return _appointment_datetime(appointment_date, start_time) > _local_now(now)


def is_within_max_days_ahead(
    appointment_date: date,
    max_days: int | None = None,
    now: datetime | None = None,
) -> bool:
    maximum = settings.max_days_ahead_to_schedule if max_days is None else max_days
    return appointment_date <= _local_now(now).date() + timedelta(days=maximum)


def has_minimum_notice(
    appointment_date: date,
    start_time: time,
    minimum_hours: int | None = None,
    now: datetime | None = None,
) -> bool:
    minimum = (
        settings.min_hours_before_cancel_or_reschedule if minimum_hours is None else minimum_hours
    )
    difference = _appointment_datetime(appointment_date, start_time) - _local_now(now)
    return difference >= timedelta(hours=minimum)
