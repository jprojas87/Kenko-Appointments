from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppointmentType, MedicalCenter, Physician
from app.schemas import MedicalCenterCatalogItem


def list_physicians(database_session: Session) -> list[Physician]:
    statement = select(Physician).order_by(Physician.last_name, Physician.first_name)
    return list(database_session.scalars(statement).all())


def list_medical_centers(database_session: Session) -> list[MedicalCenterCatalogItem]:
    centers = database_session.scalars(select(MedicalCenter).order_by(MedicalCenter.name)).all()
    physicians = database_session.scalars(select(Physician)).all()
    types_by_center: dict[UUID, set[AppointmentType]] = {
        center.medical_center_id: set() for center in centers
    }

    for physician in physicians:
        types_by_center.setdefault(physician.primary_med_center_id, set()).add(physician.specialty)
        if physician.secondary_med_center_id is not None:
            types_by_center.setdefault(physician.secondary_med_center_id, set()).add(
                physician.specialty
            )

    return [
        MedicalCenterCatalogItem(
            medical_center_id=center.medical_center_id,
            name=center.name,
            location=center.location,
            appointment_types=sorted(
                types_by_center[center.medical_center_id], key=lambda value: value.value
            ),
        )
        for center in centers
    ]
