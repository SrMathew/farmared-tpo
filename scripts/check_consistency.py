"""Check that the data in Redis says the same as MongoDB, the system of record.

Usage (inside the dev container):

    python scripts/check_consistency.py        (or: make check-consistency)

Compares the product ranking (q07) and the catalogue cache (q01) with what MongoDB holds.
Exits with code 1 and lists every difference if there is any.
"""

import sys

from farmared.adapters.mongo.connection import get_database
from farmared.adapters.redis.catalog_cache import CatalogCache
from farmared.adapters.redis.connection import get_redis
from farmared.adapters.redis.product_ranking import ProductRanking
from farmared.config import get_settings
from farmared.services.redis_sync import catalog_cache_differences, product_ranking_differences


def main() -> int:
    database, redis = get_database(), get_redis()
    differences = product_ranking_differences(database, ProductRanking(redis))
    differences += catalog_cache_differences(
        database, CatalogCache(redis, get_settings().cache_ttl_seconds)
    )
    if differences:
        print(f"Redis NO coincide con MongoDB: {len(differences)} diferencia(s).")
        for difference in differences:
            print(f"  - {difference}")
        print("Para corregirlo: make rebuild-redis")
        return 1
    print("Redis coincide con MongoDB.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
