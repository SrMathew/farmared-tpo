"""The MongoDB statements of the read queries (q01 to q12), one function per query.

Every function receives the database and returns plain dictionaries, with the business
identifier under its own name (`id_producto`) instead of `_id`.
"""

from typing import Any

from pymongo.database import Database

Document = dict[str, Any]


def active_products_with_supplier(database: Database[Document]) -> list[Document]:
    """q01. Each active product with all the data of its supplier.

    The relation is a reference (productos.id_proveedor -> proveedores._id), resolved with
    $lookup. The supplier is shown whatever its own `activo` flag is.
    """
    return list(
        database.productos.aggregate(
            [
                {"$match": {"activo": True}},
                {
                    "$lookup": {
                        "from": "proveedores",
                        "localField": "id_proveedor",
                        "foreignField": "_id",
                        "as": "proveedor",
                    }
                },
                {"$unwind": "$proveedor"},
                {"$set": {"id_producto": "$_id", "proveedor.id_proveedor": "$proveedor._id"}},
                {"$unset": ["_id", "proveedor._id", "id_proveedor"]},
                {"$sort": {"id_producto": 1}},
            ]
        )
    )
