"""The MongoDB statements of the read queries (q01 to q12), one function per query.

Every function receives the database and returns plain dictionaries, with the business
identifier under its own name (`id_producto`) instead of `_id`.
"""

from datetime import date
from typing import Any

from pymongo.database import Database

from farmared.dates import to_datetime
from farmared.domain.enums import PrescriptionStatus, PrescriptionType, SaleStatus, SaleType

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


def active_pharmacists_with_sales_since(
    database: Database[Document], since: date
) -> list[Document]:
    """q05. Active pharmacists with how many sales they registered from `since` on.

    The pipeline starts from the pharmacists, not from the sales, so the ones with no sales
    in the period are kept with a count of zero. $lookup brings the sales of each one
    (ventas.id_farmaceutico -> farmaceuticos._id) already filtered by date and state.
    """
    return list(
        database.farmaceuticos.aggregate(
            [
                {"$match": {"activo": True}},
                {
                    "$lookup": {
                        "from": "ventas",
                        "localField": "_id",
                        "foreignField": "id_farmaceutico",
                        "pipeline": [
                            {
                                "$match": {
                                    "fecha": {"$gte": to_datetime(since)},
                                    "estado": {"$ne": SaleStatus.CANCELLED.value},
                                    "activo": True,
                                }
                            }
                        ],
                        "as": "ventas",
                    }
                },
                {
                    "$replaceWith": {
                        "id_farmaceutico": "$_id",
                        "nombre": "$nombre",
                        "apellido": "$apellido",
                        "matricula": "$matricula",
                        "id_sucursal": "$id_sucursal",
                        "cantidad_ventas": {"$size": "$ventas"},
                    }
                },
                {"$sort": {"cantidad_ventas": -1, "id_farmaceutico": 1}},
            ]
        )
    )


def overdue_long_term_prescriptions(database: Database[Document], today: date) -> list[Document]:
    """q06. Valid long-term treatments whose next dispense was due before `today`.

    The filter uses the index recetas {tipo, estado, proxima_dispensa}; $lookup then adds
    the customer (recetas.id_cliente -> clientes._id) with all their data.
    """
    today_start = to_datetime(today)
    return list(
        database.recetas.aggregate(
            [
                {
                    "$match": {
                        "tipo": PrescriptionType.LONG_TERM.value,
                        "estado": PrescriptionStatus.VALID.value,
                        "proxima_dispensa": {"$lt": today_start},
                        "activo": True,
                    }
                },
                {
                    "$lookup": {
                        "from": "clientes",
                        "localField": "id_cliente",
                        "foreignField": "_id",
                        "as": "cliente",
                    }
                },
                {"$unwind": "$cliente"},
                {"$sort": {"proxima_dispensa": 1, "_id": 1}},
                {
                    "$replaceWith": {
                        "id_receta": "$_id",
                        "medico": "$medico",
                        "fecha_emision": "$fecha_emision",
                        "dispensas_autorizadas": "$dispensas_autorizadas",
                        "dispensas_realizadas": "$dispensas_realizadas",
                        "proxima_dispensa": "$proxima_dispensa",
                        "dias_de_atraso": {
                            "$dateDiff": {
                                "startDate": "$proxima_dispensa",
                                "endDate": today_start,
                                "unit": "day",
                            }
                        },
                        "cliente": {"$mergeObjects": [{"id_cliente": "$cliente._id"}, "$cliente"]},
                    }
                },
                {"$unset": "cliente._id"},
            ]
        )
    )


def units_sold_by_product(database: Database[Document]) -> dict[str, int]:
    """q07, source of truth. Units sold per product, counting only completed sales.

    Items are embedded in the sale: $unwind opens one document per item and $group adds the
    quantities per product. No join is needed.
    """
    rows = database.ventas.aggregate(
        [
            {"$match": {"estado": SaleStatus.COMPLETED.value, "activo": True}},
            {"$unwind": "$items"},
            {"$group": {"_id": "$items.id_producto", "unidades": {"$sum": "$items.cantidad"}}},
            {"$sort": {"unidades": -1, "_id": 1}},
        ]
    )
    return {row["_id"]: row["unidades"] for row in rows}


def completed_sale_ids(database: Database[Document]) -> list[str]:
    """Identifiers of the sales that count in the product ranking."""
    sales = database.ventas.find({"estado": SaleStatus.COMPLETED.value, "activo": True}, {"_id": 1})
    return [sale["_id"] for sale in sales]


def product_names(database: Database[Document], product_ids: list[str]) -> dict[str, str]:
    products = database.productos.find({"_id": {"$in": product_ids}}, {"nombre": 1})
    return {product["_id"]: product["nombre"] for product in products}


def _lookup_one(collection: str, local_field: str, alias: str) -> list[Document]:
    """Stages that bring the single document `local_field` references, as `alias`."""
    return [
        {
            "$lookup": {
                "from": collection,
                "localField": local_field,
                "foreignField": "_id",
                "as": alias,
            }
        },
        {"$unwind": f"${alias}"},
    ]


def low_stock_batches(database: Database[Document], below: int) -> list[Document]:
    """q08. Batches with fewer than `below` units, with product, branch and supplier.

    Three references are followed with $lookup: the batch points to its product and its
    branch, and the product points to its supplier (a two-step path:
    lotes.id_producto -> productos.id_proveedor -> proveedores).
    The filter uses the index lotes {unidades}.
    """
    return list(
        database.lotes.aggregate(
            [
                {"$match": {"unidades": {"$lt": below}, "activo": True}},
                *_lookup_one("productos", "id_producto", "producto"),
                *_lookup_one("proveedores", "producto.id_proveedor", "proveedor"),
                *_lookup_one("sucursales", "id_sucursal", "sucursal"),
                {"$sort": {"unidades": 1, "_id": 1}},
                {
                    "$replaceWith": {
                        "id_lote": "$_id",
                        "nro_lote": "$nro_lote",
                        "unidades": "$unidades",
                        "vencimiento": "$vencimiento",
                        "producto": {
                            "id_producto": "$producto._id",
                            "nombre": "$producto.nombre",
                        },
                        "sucursal": {
                            "id_sucursal": "$sucursal._id",
                            "nombre": "$sucursal.nombre",
                            "tipo": "$sucursal.tipo",
                        },
                        "proveedor": {
                            "id_proveedor": "$proveedor._id",
                            "razon_social": "$proveedor.razon_social",
                        },
                    }
                },
            ]
        )
    )


def small_over_the_counter_sales(database: Database[Document], below: int) -> list[Document]:
    """q09. Sales of type 'Venta libre' with a total under `below`, cancelled ones excluded.

    A single collection is involved: the items are embedded in the sale, so the whole
    answer comes from `ventas`. The filter uses the index ventas {tipo, total}.
    """
    return list(
        database.ventas.aggregate(
            [
                {
                    "$match": {
                        "tipo": SaleType.OVER_THE_COUNTER.value,
                        "total": {"$lt": below},
                        "estado": {"$ne": SaleStatus.CANCELLED.value},
                        "activo": True,
                    }
                },
                {"$sort": {"fecha": 1, "_id": 1}},
                {
                    "$replaceWith": {
                        "id_venta": "$_id",
                        "fecha": "$fecha",
                        "estado": "$estado",
                        "total": "$total",
                        "medio_pago": "$medio_pago",
                        "id_cliente": "$id_cliente",
                        "id_farmaceutico": "$id_farmaceutico",
                        "id_sucursal": "$id_sucursal",
                        "items": "$items",
                    }
                },
            ]
        )
    )
