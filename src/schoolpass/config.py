from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["local", "test", "staging", "production"]
ServiceBusMode = Literal["local", "azure"]
ActorType = Literal["user", "device", "worker", "platform", "system"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "schoolpass"
    app_env: AppEnv = "local"
    log_level: str = "INFO"
    secret_app_key: str = Field(
        default="dev-only-not-for-production",
        description="Used to encrypt MFA secrets at rest. Must be overridden in production.",
    )

    database_url: str = "postgresql+asyncpg://schoolpass_app:app_dev_only@localhost:5432/schoolpass"
    database_url_migrator: str = "postgresql+psycopg://schoolpass_migrator:migrator_dev_only@localhost:5432/schoolpass"

    redis_url: str = "redis://localhost:6379/0"

    jwt_private_key_pem: str = ""
    jwt_public_key_pem: str = ""
    jwt_issuer: str = "schoolpass"
    access_token_minutes: int = 10
    refresh_token_days: int = 30
    mfa_challenge_minutes: int = 5
    otp_ttl_seconds: int = 300
    otp_dev_allow: bool = False

    blob_local_root: str = ".data/blobs"
    service_bus_mode: ServiceBusMode = "local"
    azure_service_bus_fully_qualified_namespace: str = ""
    azure_blob_connection_string: str = ""

    cors_origins: str = ""

    @field_validator("otp_dev_allow")
    @classmethod
    def _otp_not_in_production(cls, value: bool, info: object) -> bool:
        return value

    def assert_secure_for_environment(self) -> None:
        if self.app_env == "production":
            if self.otp_dev_allow:
                raise RuntimeError("OTP_DEV_ALLOW must be false in production")
            if self.secret_app_key == "dev-only-not-for-production":
                raise RuntimeError("SECRET_APP_KEY must be set in production")
            if not self.jwt_private_key_pem or not self.jwt_public_key_pem:
                raise RuntimeError("JWT keys must be configured in production")
            if "dev_only" in self.database_url:
                raise RuntimeError("Production must not use local database credentials")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.assert_secure_for_environment()
    return settings
