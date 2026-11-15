"""Rebuild in Redis everything that is derived from MongoDB.

Usage (inside the dev container):

    python scripts/rebuild_redis.py        (or: make rebuild-redis)

Recomputes the product ranking (q07) from the completed sales and drops the catalogue
cache (q01), which is filled again by the next read. Safe to run at any time.
"""

from farmared.adapters.mongo.connection import get_database
from farmared.adapters.redis.catalog_cache import CatalogCache
from farmared.adapters.redis.connection import get_redis
from farmared.adapters.redis.product_ranking import ProductRanking
from farmared.config import get_settings
from farmared.services.redis_sync import rebuild_product_ranking


def main() -> None:
    redis = get_redis()
    ranking = ProductRanking(redis)
    rebuild_product_ranking(get_database(), ranking)
    CatalogCache(redis, get_settings().cache_ttl_seconds).invalidate()
    print(
        f"Ranking reconstruido: {len(ranking.all())} productos, "
        f"{len(ranking.counted_sales())} ventas completadas."
    )
    print("Caché del catálogo (q01) vaciada.")


if __name__ == "__main__":
    main()
