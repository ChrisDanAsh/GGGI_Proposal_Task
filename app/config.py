from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from the environment or a .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://ctaf:ctaf@localhost:5432/ctaf"
    app_name: str = "CTAF Proposal Portal"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings object, parsed once."""
    return Settings()
