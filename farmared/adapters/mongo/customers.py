"""Customers in MongoDB (collection `clientes`), for the customer service (q13)."""

from collections.abc import Callable
from typing import Any

from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from farmared.adapters.mongo.documents import from_document, to_document
from farmared.adapters.mongo.ids import Sequence, next_ids
from farmared.adapters.mongo.transactions import run_in_transaction
from farmared.domain.errors import BusinessRuleError
from farmared.domain.models import Customer


class MongoCustomers:
    def __init__(self, database: Database[dict[str, Any]]) -> None:
        self._database = database

    def get(self, id_cliente: str) -> Customer | None:
        document = self._database.clientes.find_one({"_id": id_cliente})
        return from_document(Customer, document) if document else None

    def find_by_dni(self, dni: str) -> Customer | None:
        document = self._database.clientes.find_one({"dni": dni})  # unique index on dni
        return from_document(Customer, document) if document else None

    def add(self, create: Callable[[str], Customer]) -> Customer:
        """The identifier and the customer are stored in one transaction.

        If the insert is rejected the counter goes back too: no identifier is lost. The
        unique index on `dni` is what settles two simultaneous sign-ups with the same DNI:
        the second insert fails whatever the application checked before.
        """

        def work(session: ClientSession) -> Customer:
            [id_cliente] = next_ids(self._database, Sequence.CUSTOMER, session=session)
            customer = create(id_cliente)
            self._database.clientes.insert_one(to_document(customer), session=session)
            return customer

        try:
            return run_in_transaction(work)
        except DuplicateKeyError as error:
            raise BusinessRuleError("Ya existe un cliente con ese DNI") from error

    def update(self, customer: Customer) -> None:
        document = to_document(customer)
        id_cliente = document.pop("_id")
        # A single-document update is atomic: it needs no transaction.
        self._database.clientes.update_one({"_id": id_cliente}, {"$set": document})
