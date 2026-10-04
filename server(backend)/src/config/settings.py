"""Configuration — reads from .env via pydantic-settings."""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 4000
    DATABASE_URL: str = "sqlite:///./antarctic_twin.db"
    JWT_SECRET: str = "change-me-in-production"
    JWT_EXPIRES_IN: int = 86400  # seconds (24 h)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
