"""Mapping between domain entities and MongoDB documents.

- The business identifier (C001, V001...) is the document `_id`, so references are direct
  and need no extra index.
- MongoDB has no date-only type: a day is stored as its midnight.
"""

from datetime import date, datetime
from typing import Any

from farmared.dates import to_datetime
from farmared.domain.models import (
    Batch,
    Branch,
    Customer,
    Entity,
    Pharmacist,
    Prescription,
    Product,
    Sale,
    Supplier,
)

# Collection and identifier field of each entity. Sale items are embedded in their sale.
COLLECTIONS: dict[type[Entity], tuple[str, str]] = {
    Customer: ("clientes", "id_cliente"),
    Branch: ("sucursales", "id_sucursal"),
    Pharmacist: ("farmaceuticos", "id_farmaceutico"),
    Supplier: ("proveedores", "id_proveedor"),
    Product: ("productos", "id_producto"),
    Batch: ("lotes", "id_lote"),
    Prescription: ("recetas", "id_receta"),
    Sale: ("ventas", "id_venta"),
}

# Technical collection with the sequences that generate new identifiers.
COUNTERS = "counters"


def collection_of(model: type[Entity]) -> str:
    return COLLECTIONS[model][0]


def to_document(entity: Entity) -> dict[str, Any]:
    _, id_field = COLLECTIONS[type(entity)]
    document = {
        key: to_datetime(value) if type(value) is date else value
        for key, value in entity.model_dump().items()
    }
    document["_id"] = document.pop(id_field)
    return document


def from_document[E: Entity](model: type[E], document: dict[str, Any]) -> E:
    _, id_field = COLLECTIONS[model]
    data = {
        key: value.date() if isinstance(value, datetime) else value
        for key, value in document.items()
        if key != "_id"
    }
    data[id_field] = document["_id"]
    return model.model_validate(data)
