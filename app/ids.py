"""Generación centralizada de UUID v7 (estándar global Kenko)."""

from uuid import UUID

from uuid_utils import uuid7


def generate_uuid() -> UUID:
    return UUID(str(uuid7()))


def new_event_id() -> UUID:
    return UUID(str(uuid7()))
