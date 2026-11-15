"""Data model in MongoDB: collections, validators and indexes.

MongoDB does not force a schema, so each collection gets a $jsonSchema validator: it is the
last line of defence if something writes without going through the application rules
(for instance, stock can never be stored as negative). Each index is there for a query.
"""

from enum import StrEnum
from typing import Any

from pymongo import ASCENDING, IndexModel
from pymongo.database import Database

from farmared.adapters.mongo.documents import COUNTERS
from farmared.domain.enums import (
    BranchType,
    HealthInsurance,
    PaymentMethod,
    PharmacistRole,
    PrescriptionStatus,
    PrescriptionType,
    SaleCondition,
    SaleStatus,
    SaleType,
    SupplierType,
)
from farmared.domain.models import MAX_DISPENSES

STRING = {"bsonType": "string"}
OPTIONAL_STRING = {"bsonType": ["string", "null"]}
BOOL = {"bsonType": "bool"}
DATE = {"bsonType": "date"}
OPTIONAL_DATE = {"bsonType": ["date", "null"]}


def _integer(minimum: int, maximum: int | None = None) -> dict[str, Any]:
    rule: dict[str, Any] = {"bsonType": ["int", "long"], "minimum": minimum}
    if maximum is not None:
        rule["maximum"] = maximum
    return rule


def _one_of(values: type[StrEnum]) -> dict[str, Any]:
    return {"enum": [member.value for member in values]}


def _validator(properties: dict[str, Any], optional: tuple[str, ...] = ()) -> dict[str, Any]:
    """Every listed field is required unless named in `optional`. `activo` is always required."""
    properties = {"_id": STRING, **properties, "activo": BOOL}
    required = [name for name in properties if name not in optional]
    return {"$jsonSchema": {"bsonType": "object", "required": required, "properties": properties}}


VALIDATORS: dict[str, dict[str, Any]] = {
    "clientes": _validator(
        {
            "nombre": STRING,
            "apellido": STRING,
            "dni": STRING,
            "email": OPTIONAL_STRING,
            "telefono": OPTIONAL_STRING,
            "ciudad": OPTIONAL_STRING,
            "provincia": OPTIONAL_STRING,
            "obra_social": _one_of(HealthInsurance),
            "nro_afiliado": OPTIONAL_STRING,
        }
    ),
    "sucursales": _validator(
        {
            "nombre": STRING,
            "tipo": _one_of(BranchType),
            "direccion": OPTIONAL_STRING,
            "ciudad": OPTIONAL_STRING,
            "provincia": OPTIONAL_STRING,
            "telefono": OPTIONAL_STRING,
        }
    ),
    "farmaceuticos": _validator(
        {
            "nombre": STRING,
            "apellido": STRING,
            "matricula": STRING,
            "cargo": _one_of(PharmacistRole),
            "id_sucursal": STRING,
        }
    ),
    "proveedores": _validator(
        {
            "razon_social": STRING,
            "cuit": STRING,
            "tipo": _one_of(SupplierType),
            "ciudad": OPTIONAL_STRING,
            "provincia": OPTIONAL_STRING,
            "telefono": OPTIONAL_STRING,
        }
    ),
    "productos": _validator(
        {
            "nombre": STRING,
            "principio_activo": STRING,
            "categoria": STRING,
            "presentacion": STRING,
            "condicion_venta": _one_of(SaleCondition),
            "precio_unit": _integer(minimum=1),
            "id_proveedor": STRING,
        }
    ),
    "lotes": _validator(
        {
            "id_producto": STRING,
            "id_sucursal": STRING,
            "nro_lote": STRING,
            "unidades": _integer(minimum=0),  # stock can never be negative
            "vencimiento": DATE,
        }
    ),
    "recetas": _validator(
        {
            "id_cliente": STRING,
            "medico": STRING,
            "matricula_medico": STRING,
            "fecha_emision": DATE,
            "tipo": _one_of(PrescriptionType),
            "dispensas_autorizadas": _integer(minimum=1, maximum=MAX_DISPENSES),
            "dispensas_realizadas": _integer(minimum=0, maximum=MAX_DISPENSES),
            "proxima_dispensa": OPTIONAL_DATE,
            "estado": _one_of(PrescriptionStatus),
        }
    ),
    "ventas": _validator(
        {
            "id_cliente": STRING,
            "id_farmaceutico": STRING,
            "id_sucursal": STRING,
            "id_receta": OPTIONAL_STRING,
            "fecha": DATE,
            "tipo": _one_of(SaleType),
            "medio_pago": _one_of(PaymentMethod),
            "total": _integer(minimum=0),
            "estado": _one_of(SaleStatus),
            "stock_aplicado": BOOL,
            "items": {
                "bsonType": "array",
                "minItems": 1,
                "items": {
                    "bsonType": "object",
                    "required": ["id_detalle", "id_producto", "cantidad", "precio_unit"],
                    "properties": {
                        "id_detalle": STRING,
                        "id_producto": STRING,
                        "cantidad": _integer(minimum=1),
                        "precio_unit": _integer(minimum=1),
                    },
                },
            },
        }
    ),
}


def _index(*fields: str, unique: bool = False) -> IndexModel:
    return IndexModel([(field, ASCENDING) for field in fields], unique=unique)


# The comment on each index names the query (or rule) it serves.
INDEXES: dict[str, list[IndexModel]] = {
    "clientes": [_index("dni", unique=True)],  # q13: unique DNI
    "farmaceuticos": [
        _index("matricula", unique=True),  # section 2.3: unique licence number
        _index("id_sucursal"),
    ],
    "productos": [_index("activo")],  # q01
    "lotes": [
        _index("id_sucursal", "id_producto", "vencimiento"),  # q15: FEFO order
        _index("unidades"),  # q08
    ],
    "recetas": [
        _index("id_cliente", "fecha_emision"),  # q03, q04
        _index("tipo", "estado", "proxima_dispensa"),  # q06
    ],
    "ventas": [
        _index("id_cliente", "fecha"),  # q03, q12
        _index("id_farmaceutico", "fecha"),  # q05
        _index("estado", "fecha"),  # q02, q11
        _index("id_sucursal"),  # q10
        _index("tipo", "total"),  # q09
    ],
}


def reset_schema(database: Database[dict[str, Any]]) -> None:
    """Recreate every collection, empty, with its validator and indexes.

    This is the environment reset the data load starts from, which makes the load
    reproducible. It is not a business operation: the services never delete anything.
    """
    for name, validator in VALIDATORS.items():
        database.drop_collection(name)
        collection = database.create_collection(name, validator=validator)
        if name in INDEXES:
            collection.create_indexes(INDEXES[name])
    database.drop_collection(COUNTERS)
    database.create_collection(COUNTERS)
