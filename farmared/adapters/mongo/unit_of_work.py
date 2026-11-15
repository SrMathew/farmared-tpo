"""The unit of work of the write services, on a MongoDB multi-document transaction."""

from collections.abc import Callable
from typing import Any

from pymongo.client_session import ClientSession
from pymongo.database import Database

from farmared.adapters.mongo.documents import collection_of, from_document, to_document
from farmared.adapters.mongo.ids import Sequence, next_ids
from farmared.adapters.mongo.transactions import run_in_transaction
from farmared.domain.models import (
    Batch,
    Branch,
    Customer,
    Entity,
    Pharmacist,
    Prescription,
    Product,
    Sale,
)


class MongoStore:
    """Reads and writes bound to one transaction: every operation carries its session."""

    def __init__(self, database: Database[dict[str, Any]], session: ClientSession) -> None:
        self._database = database
        self._session = session

    def _get[E: Entity](self, model: type[E], identifier: str) -> E | None:
        collection = self._database[collection_of(model)]
        document = collection.find_one({"_id": identifier}, session=self._session)
        return from_document(model, document) if document else None

    # --- Stock (q15) ---

    def get_sale(self, id_venta: str) -> Sale | None:
        return self._get(Sale, id_venta)

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

    # --- Sales (q14) ---

    def get_customer(self, id_cliente: str) -> Customer | None:
        return self._get(Customer, id_cliente)

    def get_pharmacist(self, id_farmaceutico: str) -> Pharmacist | None:
        return self._get(Pharmacist, id_farmaceutico)

    def get_branch(self, id_sucursal: str) -> Branch | None:
        return self._get(Branch, id_sucursal)

    def get_prescription(self, id_receta: str) -> Prescription | None:
        return self._get(Prescription, id_receta)

    def get_products(self, product_ids: list[str]) -> dict[str, Product]:
        documents = self._database.productos.find(
            {"_id": {"$in": product_ids}}, session=self._session
        )
        return {document["_id"]: from_document(Product, document) for document in documents}

    def next_sale_ids(self, items: int) -> tuple[str, list[str]]:
        # Inside the transaction: if the sale is rejected the counters go back with it.
        [id_venta] = next_ids(self._database, Sequence.SALE, session=self._session)
        item_ids = next_ids(self._database, Sequence.SALE_ITEM, items, session=self._session)
        return id_venta, item_ids

    def add_sale(self, sale: Sale) -> None:
        self._database.ventas.insert_one(to_document(sale), session=self._session)

    def update_prescription(self, prescription: Prescription, dispensed_before: int) -> bool:
        document = to_document(prescription)
        result = self._database.recetas.update_one(
            {"_id": document["_id"], "dispensas_realizadas": dispensed_before},
            {
                "$set": {
                    "dispensas_realizadas": document["dispensas_realizadas"],
                    "proxima_dispensa": document["proxima_dispensa"],
                    "estado": document["estado"],
                }
            },
            session=self._session,
        )
        return result.modified_count == 1


class MongoUnitOfWork:
    def __init__(self, database: Database[dict[str, Any]]) -> None:
        self._database = database

    def run[T](self, work: Callable[[MongoStore], T]) -> T:
        return run_in_transaction(lambda session: work(MongoStore(self._database, session)))
