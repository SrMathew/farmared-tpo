"""Sales and batches kept in memory: the store and unit of work of the unit tests of q15."""

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from farmared.domain.models import Batch, Sale


class InMemoryStore:
    def __init__(self, sales: list[Sale], batches: list[Batch]) -> None:
        self.sales = {sale.id_venta: sale for sale in sales}
        self.batches = {batch.id_lote: batch for batch in batches}

    def units(self) -> dict[str, int]:
        return {id_lote: batch.unidades for id_lote, batch in self.batches.items()}

    def get_sale(self, id_venta: str) -> Sale | None:
        return self.sales.get(id_venta)

    def batches_of(self, id_sucursal: str, id_producto: str) -> list[Batch]:
        return [
            batch
            for batch in self.batches.values()
            if batch.id_sucursal == id_sucursal and batch.id_producto == id_producto
        ]

    def take_from_batch(self, id_lote: str, units: int) -> bool:
        batch = self.batches[id_lote]
        if batch.unidades < units:
            return False
        self.batches[id_lote] = batch.model_copy(update={"unidades": batch.unidades - units})
        return True

    def mark_stock_applied(self, id_venta: str) -> bool:
        sale = self.sales[id_venta]
        if sale.stock_aplicado:
            return False
        self.sales[id_venta] = sale.model_copy(update={"stock_aplicado": True})
        return True


class InMemoryUnitOfWork:
    """All or nothing, like a transaction: if the work raises, the store goes back."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def run[T](self, work: Callable[[Any], T]) -> T:
        before = deepcopy(vars(self.store))
        try:
            return work(self.store)
        except Exception:
            vars(self.store).clear()
            vars(self.store).update(before)
            raise
