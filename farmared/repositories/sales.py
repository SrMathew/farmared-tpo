"""What the sale service (q14) needs from the storage."""

from collections.abc import Mapping
from typing import Protocol

from farmared.domain.models import Branch, Customer, Pharmacist, Prescription, Product, Sale
from farmared.repositories.stock import StockStore


class SalesStore(StockStore, Protocol):
    """Reads and writes of a sale, inside a unit of work. It includes the ones of the stock."""

    def get_customer(self, id_cliente: str) -> Customer | None: ...

    def get_pharmacist(self, id_farmaceutico: str) -> Pharmacist | None: ...

    def get_branch(self, id_sucursal: str) -> Branch | None: ...

    def get_products(self, product_ids: list[str]) -> dict[str, Product]:
        """The products found, by identifier. A missing identifier is simply not there."""
        ...

    def get_prescription(self, id_receta: str) -> Prescription | None: ...

    def next_sale_ids(self, items: int) -> tuple[str, list[str]]:
        """Reserve the identifier of a new sale and of each of its items."""
        ...

    def add_sale(self, sale: Sale) -> None: ...

    def update_prescription(self, prescription: Prescription, dispensed_before: int) -> bool:
        """Store a prescription after a dispense, only if it still had `dispensed_before`
        dispenses. False if it did not."""
        ...

    def complete_sale(self, id_venta: str) -> bool:
        """Turn a pending sale into a completed one. False if it was not pending."""
        ...


class SaleRanking(Protocol):
    """The ranking of products sold (q07), which is derived from the completed sales."""

    def exists(self) -> bool: ...

    def add_sale(self, id_venta: str, units: Mapping[str, int]) -> bool:
        """Count a completed sale. Counting the same sale again changes nothing."""
        ...


class IdempotencyKeys(Protocol):
    """Remembers the requests already received, so a repeated one is not registered twice."""

    def reserve(self, request_key: str) -> str | None:
        """Take the key. None if it was free; otherwise what the first request left in it:
        the identifier of its sale, or an empty text while it is still running."""
        ...

    def record(self, request_key: str, id_venta: str) -> None:
        """Leave in the key the sale the request registered."""
        ...

    def release(self, request_key: str) -> None:
        """Free the key: the request was rejected and can be sent again."""
        ...
