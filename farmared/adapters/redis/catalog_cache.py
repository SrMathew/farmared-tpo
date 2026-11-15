"""Cache of the product catalogue (q01) in Redis.

The catalogue is reference data: it changes rarely and is read all the time, the typical
case for a key-value cache. MongoDB stays the source of truth; this copy can always be
dropped and rebuilt from it.

Coherence with MongoDB:
- the key expires on its own (TTL), so a stale copy never lives longer than that;
- the data load deletes it, because it replaces the catalogue;
- no service of the system modifies products or suppliers. One that did would have to call
  `invalidate()` right after its MongoDB commit.
"""

import json
from typing import Any

from redis import Redis

from farmared.adapters.redis.connection import key


class CatalogCache:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    @property
    def _key(self) -> str:
        return key("cache", "q01")

    def get(self) -> list[dict[str, Any]] | None:
        cached = self._redis.get(self._key)
        return json.loads(cached) if cached is not None else None  # type: ignore[arg-type]

    def set(self, products: list[dict[str, Any]]) -> None:
        self._redis.set(self._key, json.dumps(products, ensure_ascii=False), ex=self._ttl_seconds)

    def invalidate(self) -> None:
        self._redis.delete(self._key)
