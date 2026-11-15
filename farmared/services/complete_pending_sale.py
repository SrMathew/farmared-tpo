"""Completion of a pending sale: the customer comes back to collect and pay it.

It is not one of the 15 queries of the assignment. It exists because a 'Pendiente' sale
(a reservation, or a product to be collected later) has to be able to become 'Completada',
and that step must follow the same rules as a new sale. It reuses the pieces of q14 and
q15, in one MongoDB transaction:
  1. the sale exists, is active and is 'Pendiente';
  2. customer, pharmacist, branch and products are still active, and the prescription (if
     any) is still 'Vigente' and of the same customer;
  3. the sale becomes 'Completada' (its date and prices stay as registered);
  4. the prescription counts the dispense, dated today;
  5. the stock is discounted with q15 (`apply_stock`).
If the stock is not enough, nothing changes: the sale stays 'Pendiente'.
After the commit the units are added to the ranking of q07, as in q14.

Engines:    MongoDB (transaction) and Redis (ranking, after the commit).
Parameters: id_venta (str), for example "V011".
Returns:    {"venta": {"antes", "despues"}, "receta": {"antes", "despues"} or None,
            "stock": the batches discounted}.
Raises:     BusinessRuleError; nothing is modified in that case.
"""

from typing import Any

from farmared.clock import Clock
from farmared.domain.enums import SaleStatus
from farmared.domain.errors import BusinessRuleError
from farmared.repositories.sales import SaleRanking, SalesStore
from farmared.repositories.unit_of_work import UnitOfWork
from farmared.services.q14_register_sale import (
    checked_parties,
    checked_prescription,
    count_in_ranking,
    dispense,
)
from farmared.services.q15_update_stock import apply_stock


def complete_pending_sale(
    unit_of_work: UnitOfWork[SalesStore], ranking: SaleRanking, clock: Clock, id_venta: str
) -> dict[str, Any]:
    today = clock.today()

    def work(store: SalesStore) -> dict[str, Any]:
        sale = store.get_sale(id_venta)
        if sale is None:
            raise BusinessRuleError(f"La venta {id_venta} no existe")
        if not sale.activo:
            raise BusinessRuleError(f"La venta {id_venta} está dada de baja")
        if sale.estado != SaleStatus.PENDING:
            raise BusinessRuleError(
                f"La venta {id_venta} está '{sale.estado}': "
                "solo una venta 'Pendiente' se puede completar"
            )
        _, _, _, products = checked_parties(
            store, sale.id_cliente, sale.id_farmaceutico, [i.id_producto for i in sale.items]
        )
        prescription = checked_prescription(
            store, sale.id_receta, sale.id_cliente, products.values(), today
        )

        if not store.complete_sale(id_venta):
            raise BusinessRuleError(f"La venta {id_venta} cambió durante la operación")
        prescription_change = dispense(store, prescription, today) if prescription else None
        stock = apply_stock(store, id_venta, today)

        completed = store.get_sale(id_venta)
        assert completed is not None
        return {
            "venta": {"antes": sale.model_dump(), "despues": completed.model_dump()},
            "receta": prescription_change,
            "stock": stock["movimientos"],
        }

    result = unit_of_work.run(work)
    count_in_ranking(ranking, result["venta"]["despues"])
    return result
