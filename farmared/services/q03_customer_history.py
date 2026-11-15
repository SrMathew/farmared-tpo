"""q03 - Complete history of a customer: sales and prescriptions in chronological order.

Purpose:    see everything a customer did in the network, oldest first.
Engine:     MongoDB.
Relation:   ventas.id_cliente and recetas.id_cliente reference the customer; both
            collections are merged with $unionWith and ordered by date. Sale items are
            embedded in each sale.
Parameters: id_cliente (str), for example "C006".
Returns:    {"cliente": {id_cliente, nombre, apellido, activo}, "historial": [...]}. Each
            entry has fecha, registro ("venta" or "receta"), id and the fields of that
            record. Cancelled sales and expired prescriptions are part of the history;
            logically deleted records are not.
Raises:     BusinessRuleError if the customer does not exist.
"""

from typing import Any

from pymongo.database import Database

from farmared.adapters.mongo import queries
from farmared.domain.errors import BusinessRuleError


def customer_history(database: Database[dict[str, Any]], id_cliente: str) -> dict[str, Any]:
    history = queries.customer_history(database, id_cliente)
    if history is None:
        raise BusinessRuleError(f"El cliente {id_cliente} no existe")
    return history
