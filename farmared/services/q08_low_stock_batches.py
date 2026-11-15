"""q08 - Batches with fewer than 50 units, with their product, branch and supplier.

Purpose:    see which batches are running out, and who supplies the product.
Engine:     MongoDB.
Relation:   lotes.id_producto -> productos, lotes.id_sucursal -> sucursales and
            productos.id_proveedor -> proveedores, all resolved with $lookup.
Parameters: below (int, default 50): the batches listed have fewer units than this.
Returns:    a list of {id_lote, nro_lote, unidades, vencimiento, producto, sucursal,
            proveedor}, ordered from the lowest stock. Expired batches and the ones of
            the warehouse are included; logically deleted batches are not.
"""

from typing import Any

from pymongo.database import Database

from farmared.adapters.mongo import queries

LOW_STOCK = 50


def low_stock_batches(
    database: Database[dict[str, Any]], below: int = LOW_STOCK
) -> list[dict[str, Any]]:
    return queries.low_stock_batches(database, below)
