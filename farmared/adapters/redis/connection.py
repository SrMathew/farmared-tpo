"""Redis connection, created once and shared, and the naming of the system's keys."""

from functools import lru_cache

import redis

from farmared.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def key(*parts: str) -> str:
    """Build a Redis key with the system prefix: key('cache', 'q01') -> 'fr:cache:q01'."""
    return get_settings().redis_prefix + ":".join(parts)
