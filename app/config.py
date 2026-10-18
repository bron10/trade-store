import logging
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(alias="DATABASE_URL")
    business_timezone: str = Field(default="UTC", alias="BUSINESS_TIMEZONE")
    expiry_interval_seconds: int = Field(default=60, ge=1, alias="EXPIRY_INTERVAL_SECONDS")
    bulk_max_items: int = Field(default=100, ge=1, le=1000, alias="BULK_MAX_ITEMS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    expiry_heartbeat_path: str = Field(
        default="/tmp/expiry-heartbeat",
        alias="EXPIRY_HEARTBEAT_PATH",
    )

    @field_validator("business_timezone")
    @classmethod
    def timezone_must_exist(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value

    @field_validator("log_level")
    @classmethod
    def log_level_must_be_known(cls, value: str) -> str:
        name = value.upper()
        if name not in logging.getLevelNamesMapping():
            raise ValueError(f"unknown log level: {value}")
        return name


@lru_cache
def get_settings() -> Settings:
    return Settings()
