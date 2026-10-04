"""Configuration — reads from .env via pydantic-settings."""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 4000
    DATABASE_URL: str = "sqlite:///./antarctic_twin.db"
    JWT_SECRET: str = "change-me-in-production"
    JWT_EXPIRES_IN: int = 86400  # seconds (24 h)
    PUBLIC_ENVIRONMENT_ENABLED: bool = False
    PUBLIC_ENVIRONMENT_URL: str = ""
    PUBLIC_ENVIRONMENT_REFRESH_SECONDS: int = 900
    PUBLIC_ENVIRONMENT_TIMEOUT_SECONDS: int = 10
    AIML_SERVICE_URL: str = "http://localhost:8001"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
