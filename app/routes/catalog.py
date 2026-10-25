from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.authz import require_known_user
from app.database import get_db
from app.schemas import MedicalCenterCatalogItem, PhysicianCatalogItem
from app.services.catalog_service import list_medical_centers, list_physicians

router = APIRouter(
    prefix="/catalog",
    tags=["catalog"],
    dependencies=[Depends(require_known_user)],
)


@router.get("/physicians", response_model=list[PhysicianCatalogItem])
def get_physicians(
    database_session: Session = Depends(get_db),
) -> list[PhysicianCatalogItem]:
    return list_physicians(database_session)


@router.get("/medical-centers", response_model=list[MedicalCenterCatalogItem])
def get_medical_centers(
    database_session: Session = Depends(get_db),
) -> list[MedicalCenterCatalogItem]:
    return list_medical_centers(database_session)
