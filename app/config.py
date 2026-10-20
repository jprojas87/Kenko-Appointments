import re

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg://appointments:appointments@appointments-db:5432/appointments_db"
    )
    environment: str = "dev"
    log_level: str = "INFO"
    jwt_algorithm: str = "HS256"
    jwt_secret: str = "change-me-dev-only"
    jwt_public_key: str = ""
    jwt_issuer: str = ""
    jwt_audience: str = ""
    demo_user_ids: str = "USR01,USR02"
    min_hours_before_cancel_or_reschedule: int = 24
    max_days_ahead_to_schedule: int = 90
    event_publisher: str = "log"
    event_bus_name: str = "kenko-dev-bus"
    aws_region: str = "us-east-1"
    aws_endpoint_url: str = ""

    @field_validator("demo_user_ids")
    @classmethod
    def validate_demo_user_ids(cls, value: str) -> str:
        user_ids = [user_id.strip().upper() for user_id in value.split(",")]
        if len(user_ids) < 2:
            raise ValueError("DEMO_USER_IDS debe incluir al menos dos usuarios")
        if any(re.fullmatch(r"[A-Z0-9]{5}", user_id) is None for user_id in user_ids):
            raise ValueError("Cada ID de DEMO_USER_IDS debe tener cinco caracteres alfanuméricos")
        if len(set(user_ids)) != len(user_ids):
            raise ValueError("DEMO_USER_IDS no puede contener IDs repetidos")
        return ",".join(user_ids)

    @property
    def configured_demo_user_ids(self) -> tuple[str, ...]:
        return tuple(self.demo_user_ids.split(","))


settings = Settings()
