"""What the customer service (q13) needs from the storage."""

from collections.abc import Callable
from typing import Protocol

from farmared.domain.models import Customer


class CustomerRepository(Protocol):
    def get(self, id_cliente: str) -> Customer | None:
        """The customer with that identifier, active or not."""
        ...

    def find_by_dni(self, dni: str) -> Customer | None:
        """The customer with that DNI, active or not."""
        ...

    def add(self, create: Callable[[str], Customer]) -> Customer:
        """Store a new customer and return it.

        The repository reserves the next identifier and calls `create` with it; reserving
        and storing happen together, so a rejected customer does not use up a number.
        Raises BusinessRuleError if the DNI already belongs to another customer.
        """
        ...

    def update(self, customer: Customer) -> None:
        """Store the current data of an existing customer."""
        ...
