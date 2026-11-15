"""Keep the data Redis derives from MongoDB coherent with it.

MongoDB is the system of record. Everything in Redis can be rebuilt from MongoDB
(`rebuild_*`) and compared against it (`*_differences`). An empty list of differences
means Redis says exactly what MongoDB says.
"""

from typing import Any

from pymongo.database import Database

from farmared.adapters.mongo import queries
from farmared.adapters.redis.catalog_cache import CatalogCache
from farmared.adapters.redis.product_ranking import ProductRanking


def rebuild_product_ranking(database: Database[dict[str, Any]], ranking: ProductRanking) -> None:
    """Recompute the product ranking from the completed sales stored in MongoDB."""
    ranking.rebuild(queries.units_sold_by_product(database), queries.completed_sale_ids(database))


def product_ranking_differences(
    database: Database[dict[str, Any]], ranking: ProductRanking
) -> list[str]:
    expected = queries.units_sold_by_product(database)
    actual = ranking.all()
    differences = [
        f"ranking: {id_producto} tiene {actual.get(id_producto, 0)} unidades en Redis "
        f"y {expected.get(id_producto, 0)} en MongoDB"
        for id_producto in sorted(expected.keys() | actual.keys())
        if expected.get(id_producto, 0) != actual.get(id_producto, 0)
    ]
    expected_sales = set(queries.completed_sale_ids(database))
    counted = ranking.counted_sales()
    for id_venta in sorted(expected_sales - counted):
        differences.append(f"ranking: la venta {id_venta} está completada y no fue contada")
    for id_venta in sorted(counted - expected_sales):
        differences.append(f"ranking: la venta {id_venta} fue contada y no está completada")
    return differences


def catalog_cache_differences(database: Database[dict[str, Any]], cache: CatalogCache) -> list[str]:
    cached = cache.get()
    if cached is not None and cached != queries.active_products_with_supplier(database):
        return ["caché q01: la copia en Redis no coincide con el catálogo de MongoDB"]
    return []
