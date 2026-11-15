"""Ranking of units sold per product (q07), kept in Redis as a sorted set.

A sorted set keeps its members ordered by score, so "the N best sellers" is read straight
from it instead of being computed over every sale. It is derived data: MongoDB holds the
sales and this ranking can always be rebuilt from them.

Coherence with MongoDB:
- a sale is added only after its MongoDB transaction committed, and only when it is
  'Completada' (the only state that counts as sold);
- adding is idempotent: the identifiers of the sales already counted are kept in a set, so
  repeating the call for the same sale changes nothing;
- `rebuild` replaces the whole ranking with what MongoDB says, in one atomic step.
"""

from collections.abc import Iterable, Mapping
from typing import Any, cast

from redis import Redis
from redis.client import Pipeline

from farmared.adapters.redis.connection import key


def _scores(reply: Any) -> list[tuple[str, float]]:
    """Redis answers sorted-set reads as (member, score) pairs."""
    return cast("list[tuple[str, float]]", reply)


class ProductRanking:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @property
    def _ranking(self) -> str:
        return key("rank", "productos")

    @property
    def _counted(self) -> str:
        return key("rank", "ventas")

    def exists(self) -> bool:
        return bool(self._redis.exists(self._ranking, self._counted))

    def add_sale(self, id_venta: str, units: Mapping[str, int]) -> bool:
        """Count the units of a completed sale. Returns False if it was already counted.

        Check and update run as one Redis transaction (WATCH / MULTI / EXEC): if another
        client counts the same sale in between, the transaction is retried and then finds
        it already counted.
        """
        counted = False

        def count(pipe: Pipeline) -> None:
            nonlocal counted
            if pipe.sismember(self._counted, id_venta):
                counted = False
                return
            pipe.multi()
            pipe.sadd(self._counted, id_venta)
            for id_producto, quantity in units.items():
                pipe.zincrby(self._ranking, quantity, id_producto)
            counted = True

        self._redis.transaction(count, self._counted)
        return counted

    def top(self, limit: int) -> list[tuple[str, int]]:
        """The `limit` best sellers as (id_producto, units), highest first.

        Products with the same units are ordered by identifier. Redis orders ties the other
        way round, so every product tied with the last place is read and ordered here.
        """
        best = _scores(self._redis.zrevrange(self._ranking, 0, limit - 1, withscores=True))
        if not best:
            return []
        lowest = best[-1][1]
        tied_or_better = _scores(
            self._redis.zrangebyscore(self._ranking, lowest, "+inf", withscores=True)
        )
        ordered = sorted(tied_or_better, key=lambda entry: (-entry[1], entry[0]))
        return [(id_producto, int(units)) for id_producto, units in ordered[:limit]]

    def all(self) -> dict[str, int]:
        """Every product in the ranking with its units."""
        entries = _scores(self._redis.zrange(self._ranking, 0, -1, withscores=True))
        return {id_producto: int(units) for id_producto, units in entries}

    def counted_sales(self) -> set[str]:
        return set(cast("set[str]", self._redis.smembers(self._counted)))

    def rebuild(self, units: Mapping[str, int], sale_ids: Iterable[str]) -> None:
        """Replace the ranking with the given totals, atomically."""
        sale_ids = list(sale_ids)
        with self._redis.pipeline(transaction=True) as pipe:
            pipe.delete(self._ranking, self._counted)
            if units:
                pipe.zadd(self._ranking, dict(units))
            if sale_ids:
                pipe.sadd(self._counted, *sale_ids)
            pipe.execute()
