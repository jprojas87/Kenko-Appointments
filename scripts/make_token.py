import argparse
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from uuid_utils import uuid7

from app.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera un JWT de prueba estilo kenko-auth.")
    parser.add_argument("--user-id", required=True, type=UUID)
    parser.add_argument("--minutes", type=int, default=15)
    arguments = parser.parse_args()

    if settings.jwt_algorithm != "HS256":
        parser.error("JWT_ALGORITHM debe ser HS256")

    now = datetime.now(UTC)
    claims: dict[str, str | datetime | int] = {
        "sub": str(arguments.user_id),
        "iss": settings.jwt_issuer or "kenko.auth",
        "aud": settings.jwt_audience or "kenko-api",
        "iat": now,
        "exp": now + timedelta(minutes=arguments.minutes),
        "jti": str(uuid7()),
        "sid": str(uuid7()),
    }

    print(jwt.encode(claims, settings.jwt_secret, algorithm="HS256"))


if __name__ == "__main__":
    main()
