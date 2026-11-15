"""Validation of the migrated data against the business rules of section 2.11.

The rules are the same functions the write services use (`farmared.domain.rules`).

- An error means a rule is broken: the load is aborted and nothing is written.
- An observation is something the legacy data cannot prove either way; it is loaded and
  reported. There are two kinds:
  * a closed sale (completed or cancelled) that references something inactive today.
    `activo` is the current state and the data has no deactivation date, so nobody can tell
    whether it was active on the day of the sale. Query 10 of the assignment accepts it
    ("esté activo o no"). In a pending sale, still open, it is an error.
  * a next dispense that is not exactly 30 days after the last one.
"""

from collections import Counter, defaultdict
from datetime import date, timedelta

from farmared.domain.enums import SaleStatus
from farmared.domain.rules import (
    DISPENSE_INTERVAL_DAYS,
    dispense_errors,
    has_economic_effect,
    inactive_errors,
    prescription_errors,
    selling_point_errors,
)
from farmared.loading.reader import Dataset


def _references(dataset: Dataset) -> list[str]:
    """Referential integrity: MongoDB does not enforce it, so the load does."""
    errors = []

    def check(owner: str, kind: str, identifier: str | None, known: dict) -> None:
        if identifier is not None and identifier not in known:
            errors.append(f"{owner}: {kind} {identifier} no existe")

    for pharmacist in dataset.pharmacists.values():
        check(pharmacist.id_farmaceutico, "la sucursal", pharmacist.id_sucursal, dataset.branches)
    for product in dataset.products.values():
        check(product.id_producto, "el proveedor", product.id_proveedor, dataset.suppliers)
    for batch in dataset.batches.values():
        check(batch.id_lote, "el producto", batch.id_producto, dataset.products)
        check(batch.id_lote, "la sucursal", batch.id_sucursal, dataset.branches)
    for prescription in dataset.prescriptions.values():
        check(prescription.id_receta, "el cliente", prescription.id_cliente, dataset.customers)
    for sale in dataset.sales.values():
        check(sale.id_venta, "el cliente", sale.id_cliente, dataset.customers)
        check(sale.id_venta, "la receta", sale.id_receta, dataset.prescriptions)
        for item in sale.items:
            check(sale.id_venta, "el producto", item.id_producto, dataset.products)
    return errors


def _uniqueness(dataset: Dataset) -> list[str]:
    errors = []

    def repeated(values: list[str]) -> list[str]:
        return sorted(value for value, times in Counter(values).items() if times > 1)

    for dni in repeated([c.dni for c in dataset.customers.values()]):
        errors.append(f"DNI {dni} repetido en más de un cliente")
    for licence in repeated([p.matricula for p in dataset.pharmacists.values()]):
        errors.append(f"Matrícula {licence} repetida en más de un farmacéutico")
    lots = [f"{b.id_producto}/{b.id_sucursal}/{b.nro_lote}" for b in dataset.batches.values()]
    for lot in repeated(lots):
        errors.append(f"Lote {lot} repetido (mismo producto, sucursal y número de lote)")
    return errors


def validate(dataset: Dataset, today: date) -> tuple[list[str], list[str]]:
    """Check every cross-entity rule. Returns (errors, observations)."""
    errors = _references(dataset) + _uniqueness(dataset)
    if errors:
        # The rules below follow the references, so they need them to be sound.
        return errors, []
    observations: list[str] = []

    dispenses: dict[str, list[date]] = defaultdict(list)
    for sale in dataset.sales.values():
        customer = dataset.customers[sale.id_cliente]
        pharmacist = dataset.pharmacists[sale.id_farmaceutico]
        branch = dataset.branches[sale.id_sucursal]
        products = [dataset.products[item.id_producto] for item in sale.items]
        prescription = dataset.prescriptions[sale.id_receta] if sale.id_receta else None
        problems = []

        if sale.fecha > today:
            problems.append("tiene fecha futura")
        problems += selling_point_errors(pharmacist, branch)
        problems += prescription_errors(prescription, sale.id_cliente, products, sale.fecha)

        inactive = inactive_errors(customer, pharmacist, branch, products)
        if sale.estado == SaleStatus.PENDING:
            # A pending sale is still open: it must be possible to complete it.
            problems += inactive
            if prescription is not None:
                problems += dispense_errors(prescription)
        else:
            observations += [f"{sale.id_venta} ({sale.estado}): {text}" for text in inactive]

        errors += [f"{sale.id_venta}: {text}" for text in problems]
        if sale.activo and has_economic_effect(sale) and prescription is not None:
            dispenses[prescription.id_receta].append(sale.fecha)

    for prescription in dataset.prescriptions.values():
        made = dispenses[prescription.id_receta]
        if len(made) != prescription.dispensas_realizadas:
            errors.append(
                f"{prescription.id_receta}: declara {prescription.dispensas_realizadas} "
                f"dispensas realizadas y tiene {len(made)} ventas completadas"
            )
        elif prescription.proxima_dispensa is not None:
            expected = max(made) + timedelta(days=DISPENSE_INTERVAL_DAYS)
            if prescription.proxima_dispensa != expected:
                observations.append(
                    f"{prescription.id_receta}: la próxima dispensa es "
                    f"{prescription.proxima_dispensa.isoformat()} y la última dispensa "
                    f"({max(made).isoformat()}) + {DISPENSE_INTERVAL_DAYS} días da "
                    f"{expected.isoformat()}"
                )

    return errors, observations
