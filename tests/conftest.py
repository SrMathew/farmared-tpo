"""Fixtures shared by every test."""

import pytest

from farmared.config import get_settings


@pytest.fixture(autouse=True)
def fresh_settings():
    """Settings are cached: clear them so a test that changes the environment is not leaked."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def database(monkeypatch):
    """An empty MongoDB database with the project schema, separate from the loaded data.

    Integration tests write here, so running them never touches the `farmared` database.
    Redis keys get their own prefix for the same reason.
    """
    from farmared.adapters.mongo.connection import get_client, get_database
    from farmared.adapters.mongo.schema import reset_schema

    monkeypatch.setenv("MONGO_DB", "farmared_test")
    monkeypatch.setenv("REDIS_PREFIX", "frtest:")
    get_settings.cache_clear()
    db = get_database()
    reset_schema(db)
    yield db
    get_client().drop_database("farmared_test")


@pytest.fixture
def redis_client(database):
    """Redis, with the system keys under a test prefix that is emptied before and after."""
    from farmared.adapters.redis.connection import get_redis
    from farmared.loading.writer import clear_derived_data

    client = get_redis()
    clear_derived_data(client)
    yield client
    clear_derived_data(client)
