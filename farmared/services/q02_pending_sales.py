"""q02 - Sales in state 'Pendiente' with their assigned pharmacist and total.

Purpose:    list the sales waiting to be completed (reserved, or missing stock to collect).
Engine:     MongoDB.
Relation:   references ventas.id_farmaceutico -> farmaceuticos and ventas.id_sucursal ->
            sucursales, both resolved with $lookup.
Parameters: none.
Returns:    a list ordered by date; each sale has id_venta, fecha, id_cliente, total,
            "farmaceutico" (id, nombre, apellido, matricula) and "sucursal" (id, nombre).
"""

from typing import Any

from pymongo.database import Database

from farmared.adapters.mongo import queries


def pending_sales(database: Database[dict[str, Any]]) -> list[dict[str, Any]]:
    return queries.pending_sales(database)
