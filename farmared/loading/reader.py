"""Read the CSV datasets and turn every row into a domain entity."""

import csv
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from farmared.dates import parse_date
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

# Columns holding dates: ISO in the course data, relative (HOY-30) in the team's records.
_DATE_COLUMNS = {"fecha", "fecha_emision", "proxima_dispensa", "vencimiento"}

# CSV file, entity and identifier column. Sales are built apart, joined with their items.
_FILES: list[tuple[str, type[Entity], str]] = [
    ("clientes", Customer, "id_cliente"),
    ("sucursales", Branch, "id_sucursal"),
    ("farmaceuticos", Pharmacist, "id_farmaceutico"),
    ("proveedores", Supplier, "id_proveedor"),
    ("productos", Product, "id_producto"),
    ("stock_lotes", Batch, "id_lote"),
    ("recetas", Prescription, "id_receta"),
]


@dataclass
class Dataset:
    """Everything read from the CSV files, indexed by identifier."""

    customers: dict[str, Customer] = field(default_factory=dict)
    branches: dict[str, Branch] = field(default_factory=dict)
    pharmacists: dict[str, Pharmacist] = field(default_factory=dict)
    suppliers: dict[str, Supplier] = field(default_factory=dict)
    products: dict[str, Product] = field(default_factory=dict)
    batches: dict[str, Batch] = field(default_factory=dict)
    prescriptions: dict[str, Prescription] = field(default_factory=dict)
    sales: dict[str, Sale] = field(default_factory=dict)

    def of(self, model: type[Entity]) -> dict[str, Any]:
        by_model: dict[type[Entity], dict[str, Any]] = {
            Customer: self.customers,
            Branch: self.branches,
            Pharmacist: self.pharmacists,
            Supplier: self.suppliers,
            Product: self.products,
            Batch: self.batches,
            Prescription: self.prescriptions,
            Sale: self.sales,
        }
        return by_model[model]


def _rows(directories: list[Path], name: str, today: date) -> list[dict[str, Any]]:
    """Rows of a CSV across the directories. Empty cells are nulls; dates become `date`."""
    rows = []
    for directory in directories:
        path = directory / f"{name}.csv"
        if not path.exists():
            continue
        with open(path, encoding="utf-8", newline="") as file:
            for raw in csv.DictReader(file):
                row: dict[str, Any] = {k: (v if v != "" else None) for k, v in raw.items()}
                for column in _DATE_COLUMNS & row.keys():
                    # An unreadable date is left as it is: the entity reports it as an error.
                    with suppress(ValueError):
                        row[column] = parse_date(row[column], today)
                rows.append(row)
    return rows


def _problems(identifier: str, error: ValidationError) -> list[str]:
    messages = []
    for detail in error.errors():
        place = ".".join(str(part) for part in detail["loc"])
        text = detail["msg"].removeprefix("Value error, ")
        messages.append(f"{identifier}: {place + ': ' if place else ''}{text}")
    return messages


def read_dataset(directories: list[Path], today: date) -> tuple[Dataset, list[str]]:
    """Build the entities of every CSV. Returns the dataset and the errors found.

    Each entity validates its own record (types, allowed values, single-record rules).
    Duplicated identifiers and rows that reference nothing are reported as errors.
    """
    dataset = Dataset()
    errors: list[str] = []

    for name, model, id_column in _FILES:
        entities = dataset.of(model)
        for row in _rows(directories, name, today):
            identifier = str(row.get(id_column))
            if identifier in entities:
                errors.append(f"{identifier}: identificador duplicado en {name}.csv")
                continue
            try:
                entities[identifier] = model.model_validate(row)
            except ValidationError as error:
                errors += _problems(identifier, error)

    # A sale is its header plus its items, and keeps the branch of its pharmacist.
    items: dict[str, list[dict[str, Any]]] = {}
    seen_items: set[str] = set()
    for row in _rows(directories, "detalle_ventas", today):
        if row["id_detalle"] in seen_items:
            errors.append(f"{row['id_detalle']}: identificador duplicado en detalle_ventas.csv")
            continue
        seen_items.add(row["id_detalle"])
        items.setdefault(row.pop("id_venta"), []).append(row)

    for row in _rows(directories, "ventas", today):
        identifier = str(row["id_venta"])
        if identifier in dataset.sales:
            errors.append(f"{identifier}: identificador duplicado en ventas.csv")
            continue
        pharmacist = dataset.pharmacists.get(row["id_farmaceutico"])
        if pharmacist is None:
            errors.append(f"{identifier}: el farmacéutico {row['id_farmaceutico']} no existe")
            continue
        try:
            dataset.sales[identifier] = Sale.model_validate(
                {
                    **row,
                    "items": items.pop(identifier, []),
                    "id_sucursal": pharmacist.id_sucursal,
                    # The stock CSV is the picture after these sales: completed ones are applied.
                    "stock_aplicado": row["estado"] == "Completada",
                }
            )
        except ValidationError as error:
            errors += _problems(identifier, error)

    for id_venta in items:
        errors.append(f"{id_venta}: hay ítems en detalle_ventas.csv de una venta que no existe")

    return dataset, errors
