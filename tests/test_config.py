"""Configuration comes from environment variables, with defaults for the dev container."""

from datetime import date

import pytest

from farmared.adapters.redis.connection import key
from farmared.config import get_settings

pytestmark = pytest.mark.unit


def test_defaults_point_at_the_dev_container_services(monkeypatch):
    for name in ("MONGO_URI", "REDIS_URL", "MONGO_DB", "REDIS_PREFIX", "FARMARED_TODAY"):
        monkeypatch.delenv(name, raising=False)

    settings = get_settings()

    assert settings.mongo_uri == "mongodb://mongo:27017/?replicaSet=rs0"
    assert settings.redis_url == "redis://redis:6379/0"
    assert settings.farmared_today is None
    assert (settings.mongo_db, settings.redis_prefix) == ("farmared", "fr:")


def test_environment_variables_override_the_defaults(monkeypatch):
    monkeypatch.setenv("MONGO_DB", "farmared_test")
    monkeypatch.setenv("FARMARED_TODAY", "2026-10-13")

    settings = get_settings()

    assert settings.mongo_db == "farmared_test"
    assert settings.farmared_today == date(2026, 10, 13)


def test_redis_keys_carry_the_system_prefix(monkeypatch):
    monkeypatch.delenv("REDIS_PREFIX", raising=False)

    assert key("cache", "q01") == "fr:cache:q01"
