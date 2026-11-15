"""q10 - Customers who were served at a given branch.

Purpose:    list the customers with at least one sale registered at a branch.
Engine:     MongoDB.
Relation:   the branch is reached through the pharmacist who registered the sale: each sale
            stores `id_sucursal`, the branch of its pharmacist at registration time. The
            sales of the branch are grouped by `id_cliente` and a $lookup brings each
            customer once.
Parameters: id_sucursal (str), for example "S002".
Returns:    {"sucursal": {id_sucursal, nombre, tipo}, "clientes": [...]}. Each customer has
            id_cliente, nombre, apellido, dni and activo, ordered by id_cliente. The
            pharmacist counts whether active or not. Sales in any state count; logically
            deleted sales do not.
Raises:     BusinessRuleError if the branch does not exist.
"""

from typing import Any

from pymongo.database import Database

from farmared.adapters.mongo import queries
from farmared.domain.errors import BusinessRuleError


def customers_served_at_branch(
    database: Database[dict[str, Any]], id_sucursal: str
) -> dict[str, Any]:
    result = queries.customers_served_at_branch(database, id_sucursal)
    if result is None:
        raise BusinessRuleError(f"La sucursal {id_sucursal} no existe")
    return result
