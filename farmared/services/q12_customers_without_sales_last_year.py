"""q12 - Customers with no sale registered in the last year.

Purpose:    find the customers who stopped buying.
Engine:     MongoDB (aggregation).
Relation:   ventas.id_cliente -> clientes._id, resolved as an anti-join: the pipeline starts
            from the customers, $lookup brings a sale of the period for each one, and the
            customers with none are kept.
Parameters: none. The period is computed from the system date (the clock), never from a
            date written in the code.
Returns:    {"desde", "hasta", "clientes": [{id_cliente, nombre, apellido, dni}]}, ordered
            by id_cliente. Only active customers are listed. A sale counts if its `fecha`
            is within the last year and it is not cancelled; pending sales count,
            logically deleted ones do not.
"""

from typing import Any

from pymongo.database import Database

from farmared.adapters.mongo import queries
from farmared.clock import Clock
from farmared.dates import one_year_before


def customers_without_sales_last_year(
    database: Database[dict[str, Any]], clock: Clock
) -> dict[str, Any]:
    today = clock.today()
    since = one_year_before(today)
    return {
        "desde": since,
        "hasta": today,
        "clientes": queries.active_customers_without_sales_since(database, since),
    }
