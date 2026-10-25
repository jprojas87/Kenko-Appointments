"""Autorización: JWT válido + usuario conocido desde ProfileCreated."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import ForbiddenError, UnauthenticatedError
from app.security import bearer_scheme, decode_access_token
from app.services.user_service import require_user_email


@dataclass(frozen=True, slots=True)
class KnownUser:
    user_id: UUID
    email: str


def require_known_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    database_session: Annotated[Session, Depends(get_db)],
) -> KnownUser:
    if credentials is None:
        raise UnauthenticatedError("Token inválido o vencido")
    current = decode_access_token(credentials.credentials)
    try:
        email = require_user_email(database_session, current.user_id)
    except ForbiddenError:
        raise
    return KnownUser(user_id=current.user_id, email=email)
