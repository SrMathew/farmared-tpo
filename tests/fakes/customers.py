"""Customers kept in memory: the repository of the unit tests of q13."""

from collections.abc import Callable

from farmared.domain.errors import BusinessRuleError
from farmared.domain.models import Customer


class InMemoryCustomers:
    def __init__(self, customers: list[Customer] | None = None, last_number: int = 0) -> None:
        self.stored = {customer.id_cliente: customer for customer in customers or []}
        self.last_number = last_number

    def get(self, id_cliente: str) -> Customer | None:
        return self.stored.get(id_cliente)

    def find_by_dni(self, dni: str) -> Customer | None:
        return next((c for c in self.stored.values() if c.dni == dni), None)

    def add(self, create: Callable[[str], Customer]) -> Customer:
        # Like the transaction of the real repository: a rejection does not use up a number.
        customer = create(f"C{self.last_number + 1:03d}")
        if self.find_by_dni(customer.dni) is not None:
            raise BusinessRuleError("Ya existe un cliente con ese DNI")
        self.last_number += 1
        self.stored[customer.id_cliente] = customer
        return customer

    def update(self, customer: Customer) -> None:
        self.stored[customer.id_cliente] = customer
