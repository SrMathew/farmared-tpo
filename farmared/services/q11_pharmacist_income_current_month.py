"""q11 - Aggregated view: total income per pharmacist in the current month.

Purpose:    know how much each pharmacist sold this month.
Engine:     MongoDB (view `v_ingresos_farmaceutico_mes_actual` over `ventas`).
Relation:   ventas.id_farmaceutico -> farmaceuticos._id. The sales of the month are grouped
            by pharmacist and a $lookup brings the name and licence number of each one.
Parameters: none. The current month comes from the system date, never from a date written
            in the code: the view uses the clock of the engine ($$NOW).
Returns:    {"mes": "YYYY-MM", "farmaceuticos": [{id_farmaceutico, nombre, apellido,
            matricula, ingresos}]}, ordered by income (highest first). Only completed
            sales compute income; logically deleted ones do not. Pharmacists without
            income this month are not listed.

A view cannot receive a date. When the clock is fixed (tests and reproducible demos), the
statement of the view is run with that day in place of $$NOW.
"""

from typing import Any

from pymongo.database import Database

from farmared.adapters.mongo import queries
from farmared.clock import Clock, FixedClock


def pharmacist_income_current_month(
    database: Database[dict[str, Any]], clock: Clock
) -> dict[str, Any]:
    today = clock.today()
    if isinstance(clock, FixedClock):
        income = queries.pharmacist_income_in_month_of(database, today)
    else:
        income = queries.pharmacist_income_current_month(database)
    return {"mes": today.strftime("%Y-%m"), "farmaceuticos": income}
