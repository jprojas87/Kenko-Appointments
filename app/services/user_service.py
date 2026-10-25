from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ForbiddenError
from app.models import User


def get_user_email(database_session: Session, user_id: UUID) -> str | None:
    return database_session.scalar(select(User.email).where(User.user_id == user_id))


def require_user_email(database_session: Session, user_id: UUID) -> str:
    email = get_user_email(database_session, user_id)
    if email is None:
        raise ForbiddenError("Usuario no registrado")
    return email


def require_user(database_session: Session, user_id: UUID) -> User:
    user = database_session.get(User, user_id)
    if user is None:
        raise ForbiddenError("Usuario no registrado")
    return user
