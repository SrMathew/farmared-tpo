"""The MongoDB statements of the read queries (q01 to q12), one function per query.

Every function receives the database and returns plain dictionaries, with the business
identifier under its own name (`id_producto`) instead of `_id`.
"""

from typing import Any

from pymongo.database import Database

from farmared.domain.enums import SaleStatus

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


def pending_sales(database: Database[Document]) -> list[Document]:
    """q02. Sales in state 'Pendiente' with their pharmacist, branch and total.

    Two references resolved with $lookup: ventas.id_farmaceutico -> farmaceuticos._id and
    ventas.id_sucursal -> sucursales._id (the branch of the pharmacist, kept in the sale).
    The pharmacist is shown whether active or not.
    """
    return list(
        database.ventas.aggregate(
            [
                {"$match": {"estado": SaleStatus.PENDING.value, "activo": True}},
                {
                    "$lookup": {
                        "from": "farmaceuticos",
                        "localField": "id_farmaceutico",
                        "foreignField": "_id",
                        "as": "farmaceutico",
                    }
                },
                {"$unwind": "$farmaceutico"},
                {
                    "$lookup": {
                        "from": "sucursales",
                        "localField": "id_sucursal",
                        "foreignField": "_id",
                        "as": "sucursal",
                    }
                },
                {"$unwind": "$sucursal"},
                {"$sort": {"fecha": 1, "_id": 1}},
                {
                    "$project": {
                        "_id": 0,
                        "id_venta": "$_id",
                        "fecha": 1,
                        "id_cliente": 1,
                        "total": 1,
                        "farmaceutico": {
                            "id_farmaceutico": "$farmaceutico._id",
                            "nombre": "$farmaceutico.nombre",
                            "apellido": "$farmaceutico.apellido",
                            "matricula": "$farmaceutico.matricula",
                        },
                        "sucursal": {
                            "id_sucursal": "$sucursal._id",
                            "nombre": "$sucursal.nombre",
                        },
                    }
                },
            ]
        )
    )
