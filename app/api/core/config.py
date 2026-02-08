"""
Application configuration using Pydantic Settings.
Loads from environment variables and .env file.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App Settings
    app_name: str = "ConnectHub API"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Supabase Settings
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Database (direct connection for complex queries)
    database_url: str | None = None

    # Redis (for ARQ background jobs)
    redis_url: str = "redis://localhost:6379"

    # API Settings
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000"]

    # JWT Settings (for additional validation if needed)
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Discovery Settings
    default_discovery_radius_km: int = 50
    max_discovery_radius_km: int = 200
    discovery_batch_size: int = 20


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
