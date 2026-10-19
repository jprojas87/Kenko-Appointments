from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import AppointmentType


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ErrorDetail(CamelModel):
    code: str
    message: str
    correlation_id: str


class ErrorResponse(CamelModel):
    error: ErrorDetail


class HealthResponse(CamelModel):
    status: str
    database_status: str


class CatalogModel(CamelModel):
    model_config = ConfigDict(from_attributes=True)


class PhysicianCatalogItem(CatalogModel):
    physician_id: UUID
    first_name: str
    last_name: str
    specialty: AppointmentType
    primary_med_center_id: UUID
    secondary_med_center_id: UUID | None


class MedicalCenterCatalogItem(CatalogModel):
    medical_center_id: UUID
    name: str
    location: str
    appointment_types: list[AppointmentType]
