from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Investment Platform API"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./investment_platform.db"
    app_secret_key: SecretStr = Field(min_length=32)
    access_token_expire_minutes: int = Field(default=30, ge=5, le=120)
    jwt_issuer: str = "investment-platform-api"
    jwt_audience: str = "investment-platform-client"
    price_cache_seconds: int = Field(default=30, ge=5, le=300)
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: SecretStr | None = None
    cors_origins: list[str] = []

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
