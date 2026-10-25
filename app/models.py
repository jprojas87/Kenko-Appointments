from datetime import UTC, date, datetime, time
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Text, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.ids import generate_uuid


class AppointmentType(StrEnum):
    GENERAL = "GENERAL"
    ODONTOLOGIA = "ODONTOLOGIA"
    PSICOLOGIA = "PSICOLOGIA"


appointment_type_enum = Enum(
    AppointmentType,
    name="appointment_type",
    values_callable=lambda enum_type: [member.value for member in enum_type],
)


class MedicalCenter(Base):
    __tablename__ = "medical_centers"

    medical_center_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)


class Physician(Base):
    __tablename__ = "physicians"

    physician_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    specialty: Mapped[AppointmentType] = mapped_column(appointment_type_enum, nullable=False)
    primary_med_center_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("medical_centers.medical_center_id"), nullable=False
    )
    secondary_med_center_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("medical_centers.medical_center_id"), nullable=True
    )


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_user_id", "user_id"),
        Index("ix_appointments_type_date_user_id", "type", "date", "user_id"),
        Index("ix_appointments_medical_center_id", "medical_center_id"),
        Index("ix_appointments_physician_id", "physician_id"),
    )

    appointment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    type: Mapped[AppointmentType] = mapped_column(appointment_type_enum, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    weekday: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    physician_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("physicians.physician_id"), nullable=False
    )
    medical_center_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("medical_centers.medical_center_id"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class User(Base):
    """Réplica mínima de profile: solo lo necesario para validar y notificar."""

    __tablename__ = "users"

    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
