"""Domain errors. Raising one means no data was modified."""


class BusinessRuleError(Exception):
    """One or more business rules are not met."""

    def __init__(self, errors: str | list[str]) -> None:
        self.errors = [errors] if isinstance(errors, str) else list(errors)
        super().__init__("; ".join(self.errors))


class InsufficientStockError(BusinessRuleError):
    """The non-expired stock of the branch does not cover a product of the sale."""

    def __init__(self, id_producto: str, requested: int, available: int) -> None:
        self.id_producto = id_producto
        self.requested = requested
        self.available = available
        super().__init__(
            f"Stock vigente insuficiente de {id_producto}: "
            f"se pidieron {requested} y hay {available}"
        )
