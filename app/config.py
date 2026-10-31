from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str
    jwt_access_expire_minutes: int = 15
    jwt_refresh_expire_days: int = 30
    resend_api_key: str
    resend_from_email: str
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    site_url: str = "http://localhost:5173"
    # Optional first-admin bootstrap (see app/bootstrap.py): when BOTH are set
    # and no user with admin_email exists yet, an admin user is created at
    # startup with these credentials. Leave unset for normal operation; this
    # is only meant to be used once on a fresh deployment (e.g. Coolify) with
    # no existing admin, and is safe to leave set across restarts/redeploys
    # since it no-ops once that user exists.
    admin_email: str | None = None
    admin_password: str | None = None
    # Garage/S3 storage for event images. The bucket does not need public
    # website access — the backend fetches objects with these credentials
    # and proxies them via GET /uploads/{key}, so images work regardless of
    # the S3 provider's DNS/website configuration.
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_bucket_name: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
