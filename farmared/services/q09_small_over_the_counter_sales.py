"""q09 - Sales of type 'Venta libre' with a total under $5,000, cancelled ones excluded.

Purpose:    list the small over-the-counter sales.
Engine:     MongoDB.
Relation:   none to resolve: the items are embedded in each sale.
Parameters: below (int, default 5000): the sales listed have a total lower than this.
Returns:    a list of {id_venta, fecha, estado, total, medio_pago, id_cliente,
            id_farmaceutico, id_sucursal, items}, ordered by date. Completed and pending
            sales are listed; cancelled and logically deleted ones are not.
"""

from typing import Any

from pymongo.database import Database

from farmared.adapters.mongo import queries

SMALL_TOTAL = 5000


def small_over_the_counter_sales(
    database: Database[dict[str, Any]], below: int = SMALL_TOTAL
) -> list[dict[str, Any]]:
    return queries.small_over_the_counter_sales(database, below)
