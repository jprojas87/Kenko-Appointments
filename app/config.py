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
    min_hours_before_cancel_or_reschedule: int = 24
    max_days_ahead_to_schedule: int = 90
    event_publisher: str = "log"
    event_bus_name: str = "kenko-dev-bus"
    aws_region: str = "us-east-1"
    aws_endpoint_url: str = ""


settings = Settings()
