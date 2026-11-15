"""Business rules of section 2.11, as pure functions.

They receive entities and return a result; they never touch a database. The write services
(q13 to q15) and the data load both use them, so each rule is written once.

Functions named `*_errors` return the list of rules that are not met (empty = all good), so
the caller can report every problem at once.
"""

from collections.abc import Iterable, Sequence
from datetime import date, timedelta

from farmared.domain.enums import (
    BranchType,
    PrescriptionStatus,
    PrescriptionType,
    SaleCondition,
    SaleStatus,
)
from farmared.domain.errors import InsufficientStockError
from farmared.domain.models import (
    Batch,
    Branch,
    Customer,
    Pharmacist,
    Prescription,
    Product,
    Sale,
    SaleItem,
)

# Days between two dispenses of a long-term treatment.
DISPENSE_INTERVAL_DAYS = 30

_PRESCRIPTION_CONDITIONS = {SaleCondition.PRESCRIPTION, SaleCondition.FILED_PRESCRIPTION}


# --- Sale condition ---------------------------------------------------------------------


def requires_prescription(product: Product) -> bool:
    return product.condicion_venta in _PRESCRIPTION_CONDITIONS


def prescription_errors(
    prescription: Prescription | None,
    id_cliente: str,
    products: Iterable[Product],
    sale_date: date,
) -> list[str]:
    """Products under prescription are only sold against a prescription of the same customer."""
    errors = []
    needing = sorted(p.id_producto for p in products if requires_prescription(p))
    if needing and prescription is None:
        errors.append(f"Los productos {needing} son de venta bajo receta y no se indicó receta")
    if prescription is not None:
        if prescription.id_cliente != id_cliente:
            errors.append(
                f"La receta {prescription.id_receta} pertenece a otro cliente "
                f"({prescription.id_cliente})"
            )
        if prescription.fecha_emision > sale_date:
            errors.append(
                f"La receta {prescription.id_receta} fue emitida después de la fecha de la venta"
            )
    return errors


def dispense_errors(prescription: Prescription) -> list[str]:
    """A prescription can only be dispensed while it is 'Vigente'.

    A valid prescription always has dispenses left: the model guarantees that one that used
    them all is 'Completada'.
    """
    if prescription.estado != PrescriptionStatus.VALID:
        return [f"La receta {prescription.id_receta} está '{prescription.estado}'"]
    return []


# --- Long-term treatment ----------------------------------------------------------------


def prescription_after_dispense(prescription: Prescription, day: date) -> Prescription:
    """The prescription as it is left by one more dispense made on `day`.

    While a long-term treatment has dispenses left, the next one is scheduled 30 days later.
    When the authorised dispenses are reached (always the case for simple and filed
    prescriptions, which allow a single one) it becomes 'Completada'.
    """
    done = prescription.dispensas_realizadas + 1
    long_term = prescription.tipo == PrescriptionType.LONG_TERM
    if long_term and done < prescription.dispensas_autorizadas:
        changes = {
            "dispensas_realizadas": done,
            "proxima_dispensa": day + timedelta(days=DISPENSE_INTERVAL_DAYS),
            "estado": PrescriptionStatus.VALID,
        }
    else:
        changes = {
            "dispensas_realizadas": done,
            "proxima_dispensa": None,
            "estado": PrescriptionStatus.COMPLETED,
        }
    # Built through validation, so the result always respects the prescription invariants.
    return Prescription.model_validate({**prescription.model_dump(), **changes})


# --- Sale status ------------------------------------------------------------------------


def has_economic_effect(sale: Sale) -> bool:
    """Only a completed sale discounts stock, counts as income and uses up a dispense."""
    return sale.estado == SaleStatus.COMPLETED


# --- Sales and branches -----------------------------------------------------------------


def selling_point_errors(pharmacist: Pharmacist, branch: Branch) -> list[str]:
    """Sales are only registered in branches of type 'Farmacia'."""
    if branch.tipo != BranchType.PHARMACY:
        return [
            f"La sucursal {branch.id_sucursal} del farmacéutico {pharmacist.id_farmaceutico} "
            f"es de tipo '{branch.tipo}': solo las farmacias registran ventas"
        ]
    return []


def inactive_errors(
    customer: Customer,
    pharmacist: Pharmacist,
    branch: Branch,
    products: Iterable[Product],
) -> list[str]:
    """Everything taking part in an open or new sale has to be active."""
    errors = []
    if not customer.activo:
        errors.append(f"El cliente {customer.id_cliente} está dado de baja")
    if not pharmacist.activo:
        errors.append(f"El farmacéutico {pharmacist.id_farmaceutico} está inactivo")
    if not branch.activo:
        errors.append(f"La sucursal {branch.id_sucursal} está inactiva")
    for product in products:
        if not product.activo:
            errors.append(f"El producto {product.id_producto} está discontinuado")
    return errors


# --- Prices -----------------------------------------------------------------------------


def sale_total(items: Iterable[SaleItem]) -> int:
    """The total of a sale is the sum of quantity x unit price of its items."""
    return sum(item.subtotal for item in items)


# --- Stock ------------------------------------------------------------------------------


def is_expired(batch: Batch, today: date) -> bool:
    """A batch can still be dispensed on its expiry date; it is expired from the day after."""
    return batch.vencimiento < today


def allocate_fefo(
    batches: Sequence[Batch], id_producto: str, quantity: int, today: date
) -> list[tuple[str, int]]:
    """Decide which batches cover `quantity` units, First Expired First Out.

    `batches` are the batches of the product in the selling branch. Expired and inactive
    batches are skipped. Returns [(id_lote, units), ...] in the order to consume them, or
    raises InsufficientStockError without allocating anything if the stock is not enough.
    """
    usable = sorted(
        (b for b in batches if b.activo and b.unidades > 0 and not is_expired(b, today)),
        key=lambda b: (b.vencimiento, b.id_lote),
    )
    available = sum(b.unidades for b in usable)
    if available < quantity:
        raise InsufficientStockError(id_producto, quantity, available)

    allocation = []
    remaining = quantity
    for batch in usable:
        if remaining == 0:
            break
        taken = min(batch.unidades, remaining)
        allocation.append((batch.id_lote, taken))
        remaining -= taken
    return allocation
