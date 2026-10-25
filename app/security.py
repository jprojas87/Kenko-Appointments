import logging
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from app.config import settings
from app.errors import UnauthenticatedError

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user_id: UUID


def _verification_key() -> str:
    if settings.jwt_algorithm != "HS256":
        raise RuntimeError("JWT_ALGORITHM debe ser HS256")
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET es obligatorio")
    return settings.jwt_secret


def decode_access_token(token: str) -> CurrentUser:
    if not settings.jwt_issuer or not settings.jwt_audience:
        raise RuntimeError("JWT_ISSUER y JWT_AUDIENCE son obligatorios")
    try:
        claims = jwt.decode(
            token,
            _verification_key(),
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            leeway=settings.jwt_leeway_seconds,
            options={
                "require": ["exp", "iss", "aud", "sub"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
            },
        )
    except InvalidTokenError as exception:
        logger.info("JWT rechazado: %s", type(exception).__name__)
        raise UnauthenticatedError("Token inválido o vencido") from exception

    subject = claims.get("sub")
    if not isinstance(subject, str):
        raise UnauthenticatedError("Token inválido o vencido")
    try:
        user_id = UUID(subject)
    except ValueError as exception:
        raise UnauthenticatedError("Token inválido o vencido") from exception
    if user_id.version != 7:
        logger.info("JWT con sub no v7 rechazado; userId=%s", user_id)
        raise UnauthenticatedError("Token inválido o vencido")

    return CurrentUser(user_id=user_id)


def current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> CurrentUser:
    if credentials is None:
        raise UnauthenticatedError("Token inválido o vencido")
    return decode_access_token(credentials.credentials)
