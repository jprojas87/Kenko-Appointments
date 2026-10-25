"""Ingesta de ProfileCreated: parseo puro + upsert idempotente."""

import json
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import User

logger = logging.getLogger(__name__)

PROFILE_SOURCE = "kenko.profile"
PROFILE_DETAIL_TYPE = "ProfileCreated"


def parse_profile_created(message_body: str) -> tuple[UUID, str] | None:
    """Devuelve (user_id, email) si el body es un ProfileCreated válido.

    Devuelve None si no es un evento ProfileCreated (para ignorarlo sin error).
    Lanza ValueError si es ProfileCreated pero trae datos inválidos.
    """
    try:
        event = json.loads(message_body)
    except json.JSONDecodeError as exception:
        raise ValueError(f"Body no es JSON válido: {exception}") from exception

    if not isinstance(event, dict):
        raise ValueError("El mensaje SQS no es un objeto JSON")

    # Soporta tanto el evento EventBridge directo como envoltorios con Message/Body.
    if "Message" in event and isinstance(event["Message"], str):
        return parse_profile_created(event["Message"])

    source = event.get("source")
    detail_type = event.get("detail-type") or event.get("detailType")
    if source != PROFILE_SOURCE or detail_type != PROFILE_DETAIL_TYPE:
        logger.info(
            "Evento ignorado: source=%s detail-type=%s (se esperaba %s/%s)",
            source,
            detail_type,
            PROFILE_SOURCE,
            PROFILE_DETAIL_TYPE,
        )
        return None

    detail = event.get("detail")
    if not isinstance(detail, dict):
        raise ValueError("ProfileCreated sin detail")

    data = detail.get("data")
    if not isinstance(data, dict):
        raise ValueError("ProfileCreated sin detail.data")

    raw_user_id = data.get("userId")
    if not isinstance(raw_user_id, str):
        raise ValueError("ProfileCreated sin data.userId")
    try:
        user_id = UUID(raw_user_id)
    except ValueError as exception:
        raise ValueError(f"userId inválido: {raw_user_id}") from exception
    if user_id.version != 7:
        raise ValueError(f"userId debe ser UUID v7: {raw_user_id}")

    contact = data.get("contact")
    if not isinstance(contact, dict):
        raise ValueError("ProfileCreated sin data.contact")
    email = contact.get("email")
    if not isinstance(email, str) or "@" not in email:
        raise ValueError("ProfileCreated sin contact.email válido")

    return user_id, email.strip()


def upsert_user(database_session: Session, user_id: UUID, email: str) -> User:
    """Inserta o actualiza el email. Idempotente: reprocesar no duplica."""
    existing = database_session.get(User, user_id)
    if existing is None:
        user = User(user_id=user_id, email=email)
        database_session.add(user)
        database_session.commit()
        logger.info("Usuario creado desde ProfileCreated; userId=%s", user_id)
        return user
    if existing.email != email:
        existing.email = email
        database_session.commit()
        logger.info("Email actualizado desde ProfileCreated; userId=%s", user_id)
    else:
        database_session.commit()
    return existing
