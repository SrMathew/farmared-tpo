"""q07 - Top 5 best-selling products by units, counting only completed sales.

Purpose:    know which products sell the most.
Engines:    Redis (sorted set with the units sold per product) and MongoDB (product names,
            and source of truth of the ranking).
Relation:   the ranking is fed from the items embedded in each completed sale; the
            product name is looked up in MongoDB by its identifier.
Parameters: limit (int, default 5).
Returns:    a list of {id_producto, nombre, unidades}, highest first; products with the
            same units are ordered by id_producto.

The ranking in Redis is derived data. If it is missing (Redis was emptied) it is rebuilt
from MongoDB before answering, so the result is always the one MongoDB would give.
"""

from typing import Any

from pymongo.database import Database

from farmared.adapters.mongo import queries
from farmared.adapters.redis.product_ranking import ProductRanking
from farmared.services.redis_sync import rebuild_product_ranking

TOP = 5


def top_products(
    database: Database[dict[str, Any]], ranking: ProductRanking, limit: int = TOP
) -> list[dict[str, Any]]:
    if not ranking.exists():
        rebuild_product_ranking(database, ranking)
    best = ranking.top(limit)
    names = queries.product_names(database, [id_producto for id_producto, _ in best])
    return [
        {"id_producto": id_producto, "nombre": names.get(id_producto), "unidades": units}
        for id_producto, units in best
    ]
