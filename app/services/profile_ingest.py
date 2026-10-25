"""Ingesta de ProfileCreated: parseo puro + upsert idempotente."""

import json
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import User

logger = logging.getLogger(__name__)

PROFILE_SOURCE = "kenko.profile"
PROFILE_DETAIL_TYPE = "ProfileCreated"


def parse_profile_created(message_body: str) -> tuple[UUID, str, str, str | None] | None:
    """Devuelve (user_id, email, first_name, last_name) si es ProfileCreated válido.

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

    person = data.get("person")
    if not isinstance(person, dict):
        raise ValueError("ProfileCreated sin data.person")
    first_name = person.get("firstName")
    if not isinstance(first_name, str) or not first_name.strip():
        raise ValueError("ProfileCreated sin person.firstName válido")
    last_name = person.get("lastName")
    if last_name is not None and not isinstance(last_name, str):
        raise ValueError("ProfileCreated con person.lastName inválido")

    return user_id, email.strip(), first_name.strip(), last_name.strip() if last_name else None


def upsert_user(
    database_session: Session,
    user_id: UUID,
    email: str,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    """Inserta o actualiza email y nombre. Idempotente: reprocesar no duplica."""
    existing = database_session.get(User, user_id)
    if existing is None:
        user = User(user_id=user_id, email=email, first_name=first_name, last_name=last_name)
        database_session.add(user)
        database_session.commit()
        logger.info("Usuario creado desde ProfileCreated; userId=%s", user_id)
        return user
    updated = False
    if existing.email != email:
        existing.email = email
        updated = True
    if first_name is not None and existing.first_name != first_name:
        existing.first_name = first_name
        updated = True
    if last_name is not None and existing.last_name != last_name:
        existing.last_name = last_name
        updated = True
    database_session.commit()
    if updated:
        logger.info("Usuario actualizado desde ProfileCreated; userId=%s", user_id)
    return existing
