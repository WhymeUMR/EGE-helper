"""Свой Settings для парсера: bot.config требует BOT_TOKEN, парсеру он ни к чему."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"


class ParserSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH, env_file_encoding="utf-8", extra="ignore"
    )

    postgres_host: str = Field(alias="POSTGRES_HOST")
    postgres_port: int = Field(alias="POSTGRES_PORT")
    postgres_db: str = Field(alias="POSTGRES_DB")
    postgres_user: str = Field(alias="POSTGRES_USER")
    postgres_password: str = Field(alias="POSTGRES_PASSWORD")

    parser_concurrency: int = Field(default=4, alias="PARSER_CONCURRENCY")
    parser_request_delay: float = Field(default=0.15, alias="PARSER_REQUEST_DELAY")
    # защита от бесконечной пагинации — sdamgia иногда отдаёт ту же страницу
    parser_max_pages_per_category: int = Field(default=50, alias="PARSER_MAX_PAGES")
    parser_interval_hours: int = Field(default=24, alias="PARSER_INTERVAL_HOURS")
    parser_run_on_startup: bool = Field(default=True, alias="PARSER_RUN_ON_STARTUP")
    # пусто = парсим с нуля, иначе url до problems.sql.gz на github releases
    parser_seed_url: str = Field(default="", alias="PARSER_SEED_URL")

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = ParserSettings()
