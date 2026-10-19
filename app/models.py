from datetime import date, time
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Date, Enum, ForeignKey, Index, Text, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppointmentType(StrEnum):
    GENERAL = "GENERAL"
    ODONTOLOGIA = "ODONTOLOGIA"
    PSICOLOGIA = "PSICOLOGIA"


def generate_uuid() -> UUID:
    return uuid4()


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
