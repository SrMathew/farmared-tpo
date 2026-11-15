"""q15 - Bulk stock update: discount the stock of a registered sale, First Expired First Out.

Purpose:    take the units of every product of a sale out of the batches of its branch.
Engine:     MongoDB (collections `ventas` and `lotes`, in one multi-document transaction).
Relation:   the sale stores `id_sucursal`, the branch of the pharmacist who registered it;
            the batches are found by that branch and each product of the embedded items
            (lotes.id_sucursal + lotes.id_producto). Nothing here feeds a Redis key.
Parameters: id_venta (str): a registered sale, for example "V118".
            The date that decides which batches are expired is the system date (the clock).
Returns:    {"id_venta", "id_sucursal", "movimientos": [...]}. Each movement is one batch
            that was discounted: id_producto, id_lote, nro_lote, vencimiento,
            unidades_antes, descontado and unidades_despues, in the order they were used.
Raises:     BusinessRuleError if the sale does not exist, is logically deleted, is not
            'Completada' or already discounted its stock, or if the non-expired stock of
            the branch does not cover some product. Nothing is modified in that case.

Rules (2.11): batches are used by nearest expiry date first; expired and logically deleted
batches are skipped; stock never goes below zero; all or nothing. Only a 'Completada' sale
discounts stock, and only once: the sale keeps `stock_aplicado`, set in the same
transaction as the discount.

`apply_stock` is the operation itself, on a store that is already inside a unit of work:
q14 calls it within the transaction that registers the sale. `update_stock` is q15 on its
own: it opens the unit of work.
"""

from collections import Counter
from datetime import date
from typing import Any

from farmared.clock import Clock
from farmared.domain.errors import BusinessRuleError, InsufficientStockError
from farmared.domain.rules import allocate_fefo, has_economic_effect
from farmared.repositories.stock import StockStore
from farmared.repositories.unit_of_work import UnitOfWork


def apply_stock(store: StockStore, id_venta: str, today: date) -> dict[str, Any]:
    sale = store.get_sale(id_venta)
    if sale is None:
        raise BusinessRuleError(f"La venta {id_venta} no existe")
    if not sale.activo:
        raise BusinessRuleError(f"La venta {id_venta} está dada de baja")
    if not has_economic_effect(sale):
        raise BusinessRuleError(
            f"La venta {id_venta} está '{sale.estado}': "
            "solo una venta 'Completada' descuenta stock"
        )
    if sale.stock_aplicado:
        raise BusinessRuleError(f"La venta {id_venta} ya descontó su stock")

    # Units per product: two items of the same product are covered together.
    quantities: Counter[str] = Counter()
    for item in sale.items:
        quantities[item.id_producto] += item.cantidad

    # First decide every batch to use; only if all the products are covered is anything
    # written. Products go in a fixed order so two sales always take batches the same way.
    movements = []
    shortages = []
    for id_producto in sorted(quantities):
        batches = {b.id_lote: b for b in store.batches_of(sale.id_sucursal, id_producto)}
        try:
            allocation = allocate_fefo(
                list(batches.values()), id_producto, quantities[id_producto], today
            )
        except InsufficientStockError as error:
            shortages.extend(error.errors)
            continue
        for id_lote, units in allocation:
            batch = batches[id_lote]
            movements.append(
                {
                    "id_producto": id_producto,
                    "id_lote": id_lote,
                    "nro_lote": batch.nro_lote,
                    "vencimiento": batch.vencimiento,
                    "unidades_antes": batch.unidades,
                    "descontado": units,
                    "unidades_despues": batch.unidades - units,
                }
            )
    if shortages:
        raise BusinessRuleError(shortages)

    for movement in movements:
        if not store.take_from_batch(movement["id_lote"], movement["descontado"]):
            raise BusinessRuleError(
                f"El lote {movement['id_lote']} cambió durante la operación: volver a intentar"
            )
    if not store.mark_stock_applied(id_venta):
        raise BusinessRuleError(f"La venta {id_venta} ya descontó su stock")
    return {"id_venta": id_venta, "id_sucursal": sale.id_sucursal, "movimientos": movements}


def update_stock(
    unit_of_work: UnitOfWork[StockStore], clock: Clock, id_venta: str
) -> dict[str, Any]:
    today = clock.today()
    return unit_of_work.run(lambda store: apply_stock(store, id_venta, today))
