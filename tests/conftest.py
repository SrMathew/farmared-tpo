"""Fixtures shared by every test."""

import pytest

from farmared.config import get_settings


@pytest.fixture(autouse=True)
def fresh_settings():
    """Settings are cached: clear them so a test that changes the environment is not leaked."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
