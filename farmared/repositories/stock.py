"""What the stock service (q15) needs from the storage, inside a unit of work."""

from typing import Protocol

from farmared.domain.models import Batch, Sale


class StockStore(Protocol):
    def get_sale(self, id_venta: str) -> Sale | None:
        """The sale with that identifier, with its items."""
        ...

    def batches_of(self, id_sucursal: str, id_producto: str) -> list[Batch]:
        """Every batch of a product in a branch, whatever its state."""
        ...

    def take_from_batch(self, id_lote: str, units: int) -> bool:
        """Discount `units` from a batch, only if it has that many. False if it did not."""
        ...

    def mark_stock_applied(self, id_venta: str) -> bool:
        """Record that the sale discounted its stock. False if it was already recorded."""
        ...
