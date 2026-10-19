from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MedicalCenterCatalogItem, PhysicianCatalogItem
from app.security import current_user
from app.services.catalog_service import list_medical_centers, list_physicians

router = APIRouter(
    prefix="/catalog",
    tags=["catalog"],
    dependencies=[Depends(current_user)],
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
