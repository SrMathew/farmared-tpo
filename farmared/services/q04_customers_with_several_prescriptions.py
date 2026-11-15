"""q04 - Customers with more than one prescription on record, and how many.

Purpose:    find the customers who brought several prescriptions.
Engine:     MongoDB (aggregation).
Relation:   recetas.id_cliente -> clientes._id. Prescriptions are grouped and counted
            first; $lookup then adds the customer data to the groups with more than one.
Parameters: none.
Returns:    a list of {id_cliente, nombre, apellido, dni, cantidad_recetas}, ordered by
            number of prescriptions (highest first) and then by id_cliente. Every
            prescription counts whatever its state; logically deleted ones do not.
"""

from typing import Any

from pymongo.database import Database

from farmared.adapters.mongo import queries


def customers_with_several_prescriptions(
    database: Database[dict[str, Any]],
) -> list[dict[str, Any]]:
    return queries.customers_with_several_prescriptions(database)
