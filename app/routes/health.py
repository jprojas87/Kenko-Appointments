from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check(database_session: Session = Depends(get_db)) -> HealthResponse:
    try:
        database_session.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError as exception:
        raise HTTPException(status_code=503, detail="Base de datos no disponible") from exception

    return HealthResponse(status="ok", database_status="ok")
