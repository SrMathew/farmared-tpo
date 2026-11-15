"""Typed configuration read from environment variables.

The dev container sets MONGO_URI and REDIS_URL (see .devcontainer/docker-compose.yml); every
other value has a default, so the project runs without any extra setup.
"""

from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Defaults are the docker-compose service names: the project only runs in the dev container.
    mongo_uri: str = "mongodb://mongo:27017/?replicaSet=rs0"
    mongo_db: str = "farmared"
    redis_url: str = "redis://redis:6379/0"

    # Prefix of every Redis key of the system, so they can be listed or rebuilt as a group.
    redis_prefix: str = "fr:"
    cache_ttl_seconds: int = 300

    # "Today" is always the system date in this time zone, never a date fixed in the code.
    timezone: str = "America/Argentina/Buenos_Aires"
    # FARMARED_TODAY (YYYY-MM-DD) overrides the system date. Only for reproducible tests and demos.
    farmared_today: date | None = None

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
