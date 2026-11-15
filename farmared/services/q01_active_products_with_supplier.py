"""q01 - Active products with all the data of their supplier.

Purpose:    list the catalogue that can be sold today, each product with its supplier.
Engines:    MongoDB ($lookup productos -> proveedores) and Redis (cache of the result).
Relation:   reference productos.id_proveedor -> proveedores._id, resolved with $lookup.
Parameters: use_cache (bool, default True). False always reads MongoDB and refreshes the cache.
Returns:    {"origen": "redis" | "mongodb", "productos": [...]}; each product carries its
            own fields plus "proveedor" with every field of the supplier, ordered by
            id_producto. "origen" tells where this answer came from.
"""

from typing import Any

from pymongo.database import Database

from farmared.adapters.mongo import queries
from farmared.adapters.redis.catalog_cache import CatalogCache


def active_products_with_supplier(
    database: Database[dict[str, Any]], cache: CatalogCache, use_cache: bool = True
) -> dict[str, Any]:
    # Cache-aside: answer from Redis when the copy is there; otherwise read MongoDB, the
    # source of truth, and leave the copy for the next reads.
    if use_cache:
        cached = cache.get()
        if cached is not None:
            return {"origen": "redis", "productos": cached}
    products = queries.active_products_with_supplier(database)
    cache.set(products)
    return {"origen": "mongodb", "productos": products}
