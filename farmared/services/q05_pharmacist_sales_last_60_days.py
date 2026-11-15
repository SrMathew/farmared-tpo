"""q05 - Active pharmacists and the number of sales they registered in the last 60 days.

Purpose:    measure the recent activity of each active pharmacist.
Engine:     MongoDB (aggregation).
Relation:   ventas.id_farmaceutico -> farmaceuticos._id. The pipeline starts from the
            pharmacists and brings their sales with $lookup, so the ones with no sales
            appear with zero.
Parameters: none. The period is computed from the system date (the clock), never from a
            date written in the code.
Returns:    {"desde", "hasta", "farmaceuticos": [{id_farmaceutico, nombre, apellido,
            matricula, id_sucursal, cantidad_ventas}]}, ordered by number of sales (highest
            first). A sale counts if its `fecha` is within the last 60 days and it is not
            cancelled; pending sales count, logically deleted ones do not.
"""

from datetime import timedelta
from typing import Any

from pymongo.database import Database

from farmared.adapters.mongo import queries
from farmared.clock import Clock

PERIOD_DAYS = 60


def pharmacist_sales_last_60_days(
    database: Database[dict[str, Any]], clock: Clock
) -> dict[str, Any]:
    today = clock.today()
    since = today - timedelta(days=PERIOD_DAYS)
    return {
        "desde": since,
        "hasta": today,
        "farmaceuticos": queries.active_pharmacists_with_sales_since(database, since),
    }
