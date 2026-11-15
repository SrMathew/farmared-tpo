"""Everything a sale touches, kept in memory: the store of the unit tests of q14."""

from collections.abc import Mapping

from fakes.stock import InMemoryStore
from farmared.domain.models import (
    Batch,
    Branch,
    Customer,
    Pharmacist,
    Prescription,
    Product,
    Sale,
)


class InMemorySalesStore(InMemoryStore):
    def __init__(
        self,
        customers: list[Customer],
        pharmacists: list[Pharmacist],
        branches: list[Branch],
        products: list[Product],
        prescriptions: list[Prescription],
        batches: list[Batch],
        sales: list[Sale] | None = None,
    ) -> None:
        super().__init__(sales or [], batches)
        self.customers = {c.id_cliente: c for c in customers}
        self.pharmacists = {p.id_farmaceutico: p for p in pharmacists}
        self.branches = {b.id_sucursal: b for b in branches}
        self.products = {p.id_producto: p for p in products}
        self.prescriptions = {p.id_receta: p for p in prescriptions}
        self.last_sale = 0
        self.last_item = 0

    def get_customer(self, id_cliente: str) -> Customer | None:
        return self.customers.get(id_cliente)

    def get_pharmacist(self, id_farmaceutico: str) -> Pharmacist | None:
        return self.pharmacists.get(id_farmaceutico)

    def get_branch(self, id_sucursal: str) -> Branch | None:
        return self.branches.get(id_sucursal)

    def get_products(self, product_ids: list[str]) -> dict[str, Product]:
        return {p: self.products[p] for p in product_ids if p in self.products}

    def get_prescription(self, id_receta: str) -> Prescription | None:
        return self.prescriptions.get(id_receta)

    def next_sale_ids(self, items: int) -> tuple[str, list[str]]:
        self.last_sale += 1
        item_ids = [f"D{self.last_item + n:03d}" for n in range(1, items + 1)]
        self.last_item += items
        return f"V{self.last_sale:03d}", item_ids

    def add_sale(self, sale: Sale) -> None:
        self.sales[sale.id_venta] = sale

    def update_prescription(self, prescription: Prescription, dispensed_before: int) -> bool:
        if self.prescriptions[prescription.id_receta].dispensas_realizadas != dispensed_before:
            return False
        self.prescriptions[prescription.id_receta] = prescription
        return True


class RecordingRanking:
    """The ranking of q07, reduced to remembering what it was asked to count."""

    def __init__(self, exists: bool = True, broken: bool = False) -> None:
        self._exists = exists
        self._broken = broken
        self.counted: dict[str, dict[str, int]] = {}

    def exists(self) -> bool:
        if self._broken:
            raise ConnectionError("Redis is down")
        return self._exists

    def add_sale(self, id_venta: str, units: Mapping[str, int]) -> bool:
        if id_venta in self.counted:
            return False
        self.counted[id_venta] = dict(units)
        return True


class InMemoryIdempotencyKeys:
    def __init__(self) -> None:
        self.keys: dict[str, str] = {}

    def reserve(self, request_key: str) -> str | None:
        if request_key in self.keys:
            return self.keys[request_key]
        self.keys[request_key] = ""
        return None

    def record(self, request_key: str, id_venta: str) -> None:
        self.keys[request_key] = id_venta

    def release(self, request_key: str) -> None:
        self.keys.pop(request_key, None)
