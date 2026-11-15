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
                # Show the business identifier first and under its own name instead of _id.
                {
                    "$set": {
                        "proveedor": {
                            "$mergeObjects": [{"id_proveedor": "$proveedor._id"}, "$proveedor"]
                        }
                    }
                },
                {"$replaceWith": {"$mergeObjects": [{"id_producto": "$_id"}, "$$ROOT"]}},
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
                    "$replaceWith": {
                        "id_venta": "$_id",
                        "fecha": "$fecha",
                        "id_cliente": "$id_cliente",
                        "total": "$total",
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


def customer_history(database: Database[Document], id_cliente: str) -> Document | None:
    """q03. A customer with their sales and prescriptions in chronological order.

    Sales and prescriptions live in two collections; $unionWith puts both in one list, each
    record with a common `fecha` (sale date / issue date), and a single $sort orders them.
    On the same day the prescription goes first: it is issued before it is dispensed.
    Sale items come embedded in the sale, so no further join is needed.
    Returns None if the customer does not exist.
    """
    customer = database.clientes.find_one({"_id": id_cliente})
    if customer is None:
        return None
    mine = {"$match": {"id_cliente": id_cliente, "activo": True}}
    history = database.ventas.aggregate(
        [
            mine,
            {
                "$replaceWith": {
                    "fecha": "$fecha",
                    "registro": "venta",
                    "id": "$_id",
                    "tipo": "$tipo",
                    "estado": "$estado",
                    "medio_pago": "$medio_pago",
                    "total": "$total",
                    "id_farmaceutico": "$id_farmaceutico",
                    "id_receta": "$id_receta",
                    "items": "$items",
                }
            },
            {
                "$unionWith": {
                    "coll": "recetas",
                    "pipeline": [
                        mine,
                        {
                            "$replaceWith": {
                                "fecha": "$fecha_emision",
                                "registro": "receta",
                                "id": "$_id",
                                "tipo": "$tipo",
                                "estado": "$estado",
                                "medico": "$medico",
                                "dispensas_autorizadas": "$dispensas_autorizadas",
                                "dispensas_realizadas": "$dispensas_realizadas",
                                "proxima_dispensa": "$proxima_dispensa",
                            }
                        },
                    ],
                }
            },
            {"$sort": {"fecha": 1, "registro": 1, "id": 1}},
        ]
    )
    return {
        "cliente": {
            "id_cliente": customer["_id"],
            "nombre": customer["nombre"],
            "apellido": customer["apellido"],
            "activo": customer["activo"],
        },
        "historial": list(history),
    }


def customers_with_several_prescriptions(database: Database[Document]) -> list[Document]:
    """q04. Customers with more than one prescription, and how many each has.

    $group counts the prescriptions per customer; only then $lookup brings the customer
    (recetas.id_cliente -> clientes._id), so the join runs on the few groups that are left.
    """
    return list(
        database.recetas.aggregate(
            [
                {"$match": {"activo": True}},
                {"$group": {"_id": "$id_cliente", "cantidad_recetas": {"$sum": 1}}},
                {"$match": {"cantidad_recetas": {"$gt": 1}}},
                {
                    "$lookup": {
                        "from": "clientes",
                        "localField": "_id",
                        "foreignField": "_id",
                        "as": "cliente",
                    }
                },
                {"$unwind": "$cliente"},
                {"$sort": {"cantidad_recetas": -1, "_id": 1}},
                {
                    "$replaceWith": {
                        "id_cliente": "$_id",
                        "nombre": "$cliente.nombre",
                        "apellido": "$cliente.apellido",
                        "dni": "$cliente.dni",
                        "cantidad_recetas": "$cantidad_recetas",
                    }
                },
            ]
        )
    )
