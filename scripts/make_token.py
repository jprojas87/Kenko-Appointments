import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import jwt

from app.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera un JWT de prueba para desarrollo.")
    parser.add_argument("--user-id", required=True, type=UUID)
    parser.add_argument("--email", default="usuario@kenko.local")
    parser.add_argument("--minutes", type=int, default=60)
    parser.add_argument("--omit-email", action="store_true")
    parser.add_argument(
        "--private-key",
        type=Path,
        help="Archivo de clave privada PEM requerido para firmar tokens RS256.",
    )
    arguments = parser.parse_args()

    now = datetime.now(UTC)
    claims: dict[str, str | datetime] = {
        "sub": str(arguments.user_id),
        "iat": now,
        "exp": now + timedelta(minutes=arguments.minutes),
    }
    if not arguments.omit_email:
        claims["email"] = arguments.email
    if settings.jwt_issuer:
        claims["iss"] = settings.jwt_issuer
    if settings.jwt_audience:
        claims["aud"] = settings.jwt_audience

    if settings.jwt_algorithm == "HS256":
        signing_key = settings.jwt_secret
    elif settings.jwt_algorithm == "RS256":
        if arguments.private_key is None:
            parser.error("--private-key es obligatorio cuando JWT_ALGORITHM=RS256")
        signing_key = arguments.private_key.read_text(encoding="utf-8")
    else:
        parser.error("JWT_ALGORITHM debe ser HS256 o RS256")

    print(jwt.encode(claims, signing_key, algorithm=settings.jwt_algorithm))


if __name__ == "__main__":
    main()
