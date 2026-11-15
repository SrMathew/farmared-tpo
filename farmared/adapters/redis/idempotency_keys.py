"""Idempotency keys of the sale registration (q14), kept in Redis.

A client that is not sure its request arrived sends it again with the same key. The first
request takes the key with `SET NX` (set only if it does not exist), which is atomic: of
two simultaneous requests with the same key, only one gets it. The key expires on its own
(`EX`), so nothing has to clean it up.

It is ephemeral data, not derived from MongoDB: losing it never loses a sale; it only
stops protecting requests repeated within the expiry time.
"""

from typing import cast

from redis import Redis

from farmared.adapters.redis.connection import key

TTL_SECONDS = 24 * 60 * 60


class RedisIdempotencyKeys:
    def __init__(self, redis: Redis, ttl_seconds: int = TTL_SECONDS) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    def _key(self, request_key: str) -> str:
        return key("idem", "q14", request_key)

    def reserve(self, request_key: str) -> str | None:
        if self._redis.set(self._key(request_key), "", nx=True, ex=self._ttl_seconds):
            return None
        return cast("str | None", self._redis.get(self._key(request_key))) or ""

    def record(self, request_key: str, id_venta: str) -> None:
        self._redis.set(self._key(request_key), id_venta, xx=True, keepttl=True)

    def release(self, request_key: str) -> None:
        self._redis.delete(self._key(request_key))
