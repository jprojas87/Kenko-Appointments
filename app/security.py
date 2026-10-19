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
    email: str | None


def _verification_key() -> str:
    if settings.jwt_algorithm == "HS256":
        return settings.jwt_secret
    if settings.jwt_algorithm == "RS256":
        if not settings.jwt_public_key:
            raise RuntimeError("JWT_PUBLIC_KEY es obligatorio cuando JWT_ALGORITHM=RS256")
        return settings.jwt_public_key
    raise RuntimeError("JWT_ALGORITHM debe ser HS256 o RS256")


def decode_access_token(token: str) -> CurrentUser:
    algorithm = settings.jwt_algorithm
    options = {
        "require": ["exp"],
        "verify_iss": bool(settings.jwt_issuer),
        "verify_aud": bool(settings.jwt_audience),
    }
    try:
        claims = jwt.decode(
            token,
            _verification_key(),
            algorithms=[algorithm],
            issuer=settings.jwt_issuer or None,
            audience=settings.jwt_audience or None,
            options=options,
        )
    except InvalidTokenError as exception:
        raise UnauthenticatedError("Token inválido o vencido") from exception

    subject = claims.get("sub")
    if not isinstance(subject, str):
        raise UnauthenticatedError("El token no contiene un userId válido")
    try:
        user_id = UUID(subject)
    except ValueError as exception:
        raise UnauthenticatedError("El token no contiene un userId válido") from exception

    email = claims.get("email")
    if email is not None and not isinstance(email, str):
        raise UnauthenticatedError("El token contiene un email inválido")
    if email is None:
        logger.warning("El token no incluye el claim email; userId=%s", user_id)

    return CurrentUser(user_id=user_id, email=email)


def current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> CurrentUser:
    if credentials is None:
        raise UnauthenticatedError("Token Bearer requerido")
    return decode_access_token(credentials.credentials)
