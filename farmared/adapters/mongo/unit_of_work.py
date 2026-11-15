"""The unit of work of the write services, on a MongoDB multi-document transaction."""

from collections.abc import Callable
from typing import Any

from pymongo.client_session import ClientSession
from pymongo.database import Database

from farmared.adapters.mongo.documents import from_document
from farmared.adapters.mongo.transactions import run_in_transaction
from farmared.domain.models import Batch, Sale


class MongoStore:
    """Reads and writes bound to one transaction: every operation carries its session."""

    def __init__(self, database: Database[dict[str, Any]], session: ClientSession) -> None:
        self._database = database
        self._session = session

    def get_sale(self, id_venta: str) -> Sale | None:
        document = self._database.ventas.find_one({"_id": id_venta}, session=self._session)
        return from_document(Sale, document) if document else None

    def batches_of(self, id_sucursal: str, id_producto: str) -> list[Batch]:
        # Served by the index lotes {id_sucursal, id_producto, vencimiento}, in FEFO order.
        documents = self._database.lotes.find(
            {"id_sucursal": id_sucursal, "id_producto": id_producto}, session=self._session
        ).sort("vencimiento", 1)
        return [from_document(Batch, document) for document in documents]

    def take_from_batch(self, id_lote: str, units: int) -> bool:
        # Conditional update: the batch is only touched if it still has the units, so the
        # stock can never go below zero whatever happened since it was read.
        result = self._database.lotes.update_one(
            {"_id": id_lote, "unidades": {"$gte": units}},
            {"$inc": {"unidades": -units}},
            session=self._session,
        )
        return result.modified_count == 1

    def mark_stock_applied(self, id_venta: str) -> bool:
        result = self._database.ventas.update_one(
            {"_id": id_venta, "stock_aplicado": False},
            {"$set": {"stock_aplicado": True}},
            session=self._session,
        )
        return result.modified_count == 1


class MongoUnitOfWork:
    def __init__(self, database: Database[dict[str, Any]]) -> None:
        self._database = database

    def run[T](self, work: Callable[[MongoStore], T]) -> T:
        return run_in_transaction(lambda session: work(MongoStore(self._database, session)))
