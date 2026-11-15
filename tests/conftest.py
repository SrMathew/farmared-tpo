"""Fixtures shared by every test.

The whole test session works on its own MongoDB database and its own Redis key prefix, so
running the tests never touches the data loaded with `make load`.
"""

import os
from datetime import date
from pathlib import Path

import pytest

os.environ["MONGO_DB"] = "farmared_test"
os.environ["REDIS_PREFIX"] = "frtest:"

from farmared.config import get_settings  # noqa: E402

# "Today" for every test that uses loaded data.
TODAY = date(2026, 11, 15)
DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(autouse=True)
def fresh_settings():
    """Settings are cached: clear them so a test that changes the environment is not leaked."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def _test_database():
    """The test database. It is kept between runs and emptied by the tests that need it.

    It is never dropped: dropping a database and creating its collections again right away
    is the one thing every MongoDB crash seen in the dev container had in common.
    """
    from farmared.adapters.mongo.connection import get_database

    get_settings.cache_clear()
    return get_database()


@pytest.fixture
def database(_test_database):
    """An empty database with the project schema. For tests that write."""
    from farmared.adapters.mongo.schema import reset_schema

    reset_schema(_test_database)
    return _test_database


@pytest.fixture
def redis_client():
    """Redis, with the system keys under the test prefix emptied before and after."""
    from farmared.adapters.redis.connection import get_redis
    from farmared.loading.writer import clear_derived_data

    client = get_redis()
    clear_derived_data(client)
    yield client
    clear_derived_data(client)


@pytest.fixture(scope="module")
def loaded(_test_database):
    """The database with the course data and the additional records, loaded once per module.

    For the read queries, which do not modify MongoDB: loading once instead of before every
    test keeps the test run light. Do not combine it with `database`, which empties it.

    The clock is fixed, so the relative dates of the additional records (HOY-30) and every
    query that depends on "today" give the same result on any day the tests run.
    """
    from farmared.adapters.redis.connection import get_redis
    from farmared.loading.loader import load_data

    get_settings.cache_clear()
    load_data(_test_database, get_redis(), DATA, TODAY)
    return _test_database
