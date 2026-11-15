"""q14 - Registration of a new 'Completada' sale, header and items, with its stock.

Purpose:    register a sale that was paid and handed over.
Engines:    MongoDB (one multi-document transaction over `ventas`, `recetas`, `lotes` and
            `counters`) and Redis (ranking of q07 and idempotency key, outside the
            transaction).
Relation:   the sale references customer, pharmacist, branch and prescription by
            identifier, and embeds its items. Every reference is read and checked inside
            the transaction that stores the sale.
Parameters: id_cliente (str), id_farmaceutico (str), items (list of (id_producto,
            cantidad)), medio_pago (str), id_receta (str, only for products under
            prescription) and idempotency_key (str, optional: the same key sent again does
            not register a second sale). All of them are arguments.
Returns:    {"venta": the sale stored, "receta": {"antes", "despues"} or None,
            "stock": the batches discounted, as q15 returns them}.
Raises:     BusinessRuleError listing every rule that is not met. Nothing is stored then:
            no sale, no change in the prescription, no batch touched, no identifier used.

Validations (assignment, q14): customer existing and active; pharmacist existing, active
and of a branch of type 'Farmacia' (also active); products existing and active; for
products under prescription, a prescription existing, 'Vigente' and of the same customer.

What it writes, all in one transaction (q14 and q15 integrated):
  1. the identifiers of the sale and of its items (counters);
  2. the sale: date = today, branch = the pharmacist's, unit price = the current list price
     of each product, total = sum of the items, state 'Completada';
  3. the prescription after the dispense (rule "Tratamiento prolongado");
  4. the stock, with q15 (`apply_stock`): FEFO, no expired batches, all or nothing.
If any step fails the transaction is aborted and none of them is stored.

Only after the commit, Redis is updated: the units are added to the ranking of q07, once
per sale. If Redis fails the sale is not affected: the ranking is rebuilt from MongoDB.
"""

import logging
from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

from farmared.clock import Clock
from farmared.domain.enums import PaymentMethod, SaleStatus, SaleType
from farmared.domain.errors import BusinessRuleError
from farmared.domain.models import (
    Branch,
    Customer,
    Pharmacist,
    Prescription,
    Product,
    Sale,
    SaleItem,
)
from farmared.domain.rules import (
    dispense_errors,
    inactive_errors,
    prescription_after_dispense,
    prescription_errors,
    requires_prescription,
    sale_total,
    selling_point_errors,
)
from farmared.repositories.sales import IdempotencyKeys, SaleRanking, SalesStore
from farmared.repositories.unit_of_work import UnitOfWork
from farmared.services.q15_update_stock import apply_stock

logger = logging.getLogger(__name__)


def checked_parties(
    store: SalesStore, id_cliente: str, id_farmaceutico: str, product_ids: Iterable[str]
) -> tuple[Customer, Pharmacist, Branch, dict[str, Product]]:
    """Customer, pharmacist, branch and products of a sale: all existing, active and able
    to sell. Every problem found is reported at once."""
    product_ids = sorted(set(product_ids))
    customer = store.get_customer(id_cliente)
    pharmacist = store.get_pharmacist(id_farmaceutico)
    branch = store.get_branch(pharmacist.id_sucursal) if pharmacist else None
    products = store.get_products(product_ids)

    missing = []
    if customer is None:
        missing.append(f"El cliente {id_cliente} no existe")
    if pharmacist is None:
        missing.append(f"El farmacéutico {id_farmaceutico} no existe")
    elif branch is None:
        missing.append(f"La sucursal {pharmacist.id_sucursal} del farmacéutico no existe")
    missing += [f"El producto {p} no existe" for p in product_ids if p not in products]
    if customer is None or pharmacist is None or branch is None or missing:
        raise BusinessRuleError(missing)

    errors = inactive_errors(customer, pharmacist, branch, products.values())
    errors += selling_point_errors(pharmacist, branch)
    if errors:
        raise BusinessRuleError(errors)
    return customer, pharmacist, branch, products


def checked_prescription(
    store: SalesStore,
    id_receta: str | None,
    id_cliente: str,
    products: Iterable[Product],
    sale_date: date,
) -> Prescription | None:
    """The prescription of a sale, able to be dispensed, or None for an over-the-counter
    sale. Products under prescription need one, valid and of the same customer."""
    products = list(products)
    prescription = None
    if id_receta is not None:
        prescription = store.get_prescription(id_receta)
        if prescription is None:
            raise BusinessRuleError(f"La receta {id_receta} no existe")
    errors = prescription_errors(prescription, id_cliente, products, sale_date)
    if prescription is not None:
        if not prescription.activo:
            errors.append(f"La receta {id_receta} está dada de baja")
        errors += dispense_errors(prescription)
        if not any(requires_prescription(product) for product in products):
            errors.append(
                "Ningún producto de la venta es de venta bajo receta: no corresponde indicar una"
            )
    if errors:
        raise BusinessRuleError(errors)
    return prescription


def dispense(store: SalesStore, prescription: Prescription, day: date) -> dict[str, Any]:
    """Count one dispense on the prescription. Returns it before and after."""
    after = prescription_after_dispense(prescription, day)
    if not store.update_prescription(after, prescription.dispensas_realizadas):
        raise BusinessRuleError(
            f"La receta {prescription.id_receta} cambió durante la operación: volver a intentar"
        )
    return {"antes": prescription.model_dump(), "despues": after.model_dump()}


def count_in_ranking(ranking: SaleRanking, sale: dict[str, Any]) -> None:
    """After the commit: add the units of a completed sale to the ranking of q07.

    A failure of Redis must not fail a sale that MongoDB already stored: it is logged, and
    `make rebuild-redis` (or the next q07 on an empty Redis) brings the ranking up to date.
    If the ranking does not exist it is not started here with a single sale: q07 rebuilds
    it whole from MongoDB, this sale included.
    """
    units: Counter[str] = Counter()
    for item in sale["items"]:
        units[item["id_producto"]] += item["cantidad"]
    try:
        if ranking.exists():
            ranking.add_sale(sale["id_venta"], units)
    except Exception:
        logger.warning(
            "No se pudo actualizar el ranking de Redis con la venta %s; "
            "se corrige con 'make rebuild-redis'",
            sale["id_venta"],
            exc_info=True,
        )


def _request_errors(items: Sequence[tuple[str, int]], medio_pago: str) -> list[str]:
    errors = []
    if not items:
        errors.append("La venta no tiene ítems")
    errors += [
        f"La cantidad de {id_producto} debe ser un entero mayor a cero"
        for id_producto, quantity in items
        if not isinstance(quantity, int) or quantity < 1
    ]
    methods = [method.value for method in PaymentMethod]
    if medio_pago not in methods:
        errors.append(
            f"Medio de pago no válido: {medio_pago}. Valores permitidos: {', '.join(methods)}"
        )
    return errors


def register_sale(
    unit_of_work: UnitOfWork[SalesStore],
    ranking: SaleRanking,
    clock: Clock,
    id_cliente: str,
    id_farmaceutico: str,
    items: Sequence[tuple[str, int]],
    medio_pago: str,
    id_receta: str | None = None,
    idempotency: IdempotencyKeys | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    errors = _request_errors(items, medio_pago)
    if errors:
        raise BusinessRuleError(errors)
    today = clock.today()

    def work(store: SalesStore) -> dict[str, Any]:
        product_ids = [id_producto for id_producto, _ in items]
        _, pharmacist, branch, products = checked_parties(
            store, id_cliente, id_farmaceutico, product_ids
        )
        prescription = checked_prescription(store, id_receta, id_cliente, products.values(), today)

        id_venta, item_ids = store.next_sale_ids(len(items))
        lines = [
            SaleItem(
                id_detalle=id_detalle,
                id_producto=id_producto,
                cantidad=quantity,
                precio_unit=products[id_producto].precio_unit,  # current list price
            )
            for id_detalle, (id_producto, quantity) in zip(item_ids, items, strict=True)
        ]
        store.add_sale(
            Sale(
                id_venta=id_venta,
                id_cliente=id_cliente,
                id_farmaceutico=id_farmaceutico,
                id_sucursal=branch.id_sucursal,
                id_receta=id_receta,
                fecha=today,
                tipo=SaleType.WITH_PRESCRIPTION if prescription else SaleType.OVER_THE_COUNTER,
                medio_pago=PaymentMethod(medio_pago),
                total=sale_total(lines),
                estado=SaleStatus.COMPLETED,
                items=lines,
            )
        )
        prescription_change = dispense(store, prescription, today) if prescription else None
        stock = apply_stock(store, id_venta, today)

        stored = store.get_sale(id_venta)
        assert stored is not None  # it was added a few lines above, in this same unit of work
        return {
            "venta": stored.model_dump(),
            "receta": prescription_change,
            "stock": stock["movimientos"],
        }

    # The key is taken before the transaction and freed if the sale is rejected.
    guard = (idempotency, idempotency_key) if idempotency and idempotency_key else None
    if guard:
        keys, request_key = guard
        earlier = keys.reserve(request_key)
        if earlier is not None:
            outcome = f"registró la venta {earlier}" if earlier else "todavía está en curso"
            raise BusinessRuleError(
                f"La solicitud {request_key} ya fue recibida y {outcome}: no se repite"
            )
    try:
        result = unit_of_work.run(work)
    except Exception:
        if guard:
            guard[0].release(guard[1])  # nothing was stored: the request can be sent again
        raise

    # From here on the sale is committed in MongoDB; Redis only follows.
    if guard:
        guard[0].record(guard[1], result["venta"]["id_venta"])
    count_in_ranking(ranking, result["venta"])
    return result
