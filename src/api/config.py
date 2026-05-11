"""ApiSettings — postgres-поля общие с ботом, плюс свои API_*."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH, env_file_encoding="utf-8", extra="ignore"
    )

    postgres_host: str = Field(alias="POSTGRES_HOST")
    postgres_port: int = Field(alias="POSTGRES_PORT")
    postgres_db: str = Field(alias="POSTGRES_DB")
    postgres_user: str = Field(alias="POSTGRES_USER")
    postgres_password: str = Field(alias="POSTGRES_PASSWORD")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    # legacy bearer (для совместимости со старым обвесом). Если задан — старые
    # эндпоинты каталога/проблем требуют его И/ИЛИ JWT.
    api_token: str = Field(default="", alias="API_TOKEN")

    # JWT: секрет ОБЯЗАН быть задан в проде. Дефолт оставлен только для тестов.
    jwt_secret: str = Field(default="dev-only-change-me", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_ttl_minutes: int = Field(default=60, alias="JWT_ACCESS_TTL_MINUTES")
    jwt_refresh_ttl_days: int = Field(default=30, alias="JWT_REFRESH_TTL_DAYS")
    # /auth/register опционально можно закрыть инвайтами. Пока оставляем открытым.
    registration_open: bool = Field(default=True, alias="REGISTRATION_OPEN")
    telegram_link_ttl_minutes: int = Field(default=10, alias="TELEGRAM_LINK_TTL_MINUTES")

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = ApiSettings()
