"""q06 - Valid long-term treatments whose next dispense is overdue, with the customer data.

Purpose:    find the patients who should already have come back for their medication.
Engine:     MongoDB.
Relation:   recetas.id_cliente -> clientes._id, resolved with $lookup.
Parameters: none. "Today" is the system date (the clock), never a date written in the code.
Returns:    {"hoy", "recetas": [...]}. Each prescription has id_receta, medico,
            fecha_emision, dispensas_autorizadas, dispensas_realizadas, proxima_dispensa,
            dias_de_atraso and "cliente" with every field of the customer. Ordered from the
            most overdue. A prescription is listed when its type is 'Tratamiento
            prolongado', its state 'Vigente' and its next dispense is strictly before today.
"""

from typing import Any

from pymongo.database import Database

from farmared.adapters.mongo import queries
from farmared.clock import Clock


def overdue_long_term_prescriptions(
    database: Database[dict[str, Any]], clock: Clock
) -> dict[str, Any]:
    today = clock.today()
    return {"hoy": today, "recetas": queries.overdue_long_term_prescriptions(database, today)}
