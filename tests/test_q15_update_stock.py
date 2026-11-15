"""q15 - Bulk stock update: discount the stock of a registered sale, First Expired First Out."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from fakes.stock import InMemoryStore, InMemoryUnitOfWork

from farmared.adapters.mongo.documents import to_document
from farmared.adapters.mongo.unit_of_work import MongoStore, MongoUnitOfWork
from farmared.cli import main
from farmared.clock import FixedClock
from farmared.config import get_settings
from farmared.domain.errors import BusinessRuleError
from farmared.domain.models import Batch, Sale, SaleItem
from farmared.services.q15_update_stock import update_stock

TODAY = date(2026, 11, 15)  # the day the test data is loaded with (see conftest)
CLOCK = FixedClock(TODAY)


def sale(id_venta: str, items: dict[str, int], id_sucursal: str = "S1", **changes) -> Sale:
    """A completed sale that has not discounted its stock yet. `items`: product -> units."""
    lines = [
        SaleItem(id_detalle=f"{id_venta}-{n}", id_producto=product, cantidad=units, precio_unit=100)
        for n, (product, units) in enumerate(items.items(), start=1)
    ]
    data = {
        "id_venta": id_venta,
        "id_cliente": "C101",
        "id_farmaceutico": "F101",
        "id_sucursal": id_sucursal,
        "fecha": TODAY,
        "tipo": "Venta libre",
        "medio_pago": "Efectivo",
        "total": sum(line.subtotal for line in lines),
        "estado": "Completada",
        "items": lines,
    }
    return Sale.model_validate(data | changes)


def batch(id_lote: str, units: int, expiry: date, product: str = "P1", **changes) -> Batch:
    data = {
        "id_lote": id_lote,
        "id_producto": product,
        "id_sucursal": "S1",
        "nro_lote": f"N-{id_lote}",
        "unidades": units,
        "vencimiento": expiry,
    }
    return Batch.model_validate(data | changes)


def run(store: InMemoryStore, id_venta: str = "V1") -> dict:
    return update_stock(InMemoryUnitOfWork(store), CLOCK, id_venta)


# --- The rules, without database engines ------------------------------------------------


@pytest.mark.unit
def test_batches_are_used_by_nearest_expiry_first():
    store = InMemoryStore(
        [sale("V1", {"P1": 12})],
        [
            batch("L1", 50, date(2027, 6, 30)),
            batch("L2", 10, date(2026, 12, 31)),  # expires first: used first, and emptied
            batch("L3", 50, date(2028, 1, 31)),
        ],
    )

    result = run(store)

    assert result == {
        "id_venta": "V1",
        "id_sucursal": "S1",
        "movimientos": [
            {
                "id_producto": "P1",
                "id_lote": "L2",
                "nro_lote": "N-L2",
                "vencimiento": date(2026, 12, 31),
                "unidades_antes": 10,
                "descontado": 10,
                "unidades_despues": 0,
            },
            {
                "id_producto": "P1",
                "id_lote": "L1",
                "nro_lote": "N-L1",
                "vencimiento": date(2027, 6, 30),
                "unidades_antes": 50,
                "descontado": 2,
                "unidades_despues": 48,
            },
        ],
    }
    assert store.units() == {"L1": 48, "L2": 0, "L3": 50}
    assert store.sales["V1"].stock_aplicado is True


@pytest.mark.unit
def test_expired_and_logically_deleted_batches_are_skipped():
    store = InMemoryStore(
        [sale("V1", {"P1": 5})],
        [
            batch("L1", 50, date(2026, 11, 14)),  # expired yesterday
            batch("L2", 50, date(2026, 11, 20), activo=False),
            batch("L3", 50, TODAY),  # expires today: can still be dispensed
            batch("L4", 50, date(2027, 1, 31)),
        ],
    )

    run(store)

    assert store.units() == {"L1": 50, "L2": 50, "L3": 45, "L4": 50}


@pytest.mark.unit
def test_only_the_batches_of_the_branch_of_the_sale_are_used():
    store = InMemoryStore(
        [sale("V1", {"P1": 5})],
        [batch("L1", 50, date(2027, 1, 31), id_sucursal="S2"), batch("L2", 3, date(2027, 6, 30))],
    )

    with pytest.raises(BusinessRuleError, match="se pidieron 5 y hay 3"):
        run(store)


@pytest.mark.unit
def test_two_items_of_the_same_product_are_covered_together():
    lines = [
        SaleItem(id_detalle="D1", id_producto="P1", cantidad=4, precio_unit=100),
        SaleItem(id_detalle="D2", id_producto="P1", cantidad=3, precio_unit=100),
    ]
    store = InMemoryStore(
        [sale("V1", {"P1": 1}, items=lines, total=700)], [batch("L1", 10, date(2027, 1, 31))]
    )

    run(store)

    assert store.units() == {"L1": 3}


@pytest.mark.unit
def test_if_one_product_is_short_no_batch_is_modified():
    store = InMemoryStore(
        [sale("V1", {"P1": 5, "P2": 8, "P3": 9})],
        [
            batch("L1", 50, date(2027, 1, 31)),
            batch("L2", 7, date(2027, 1, 31), product="P2"),
            batch("L3", 20, date(2026, 1, 31), product="P3"),  # expired: does not count
        ],
    )

    with pytest.raises(BusinessRuleError) as rejected:
        run(store)

    # Every product that is short is reported.
    assert rejected.value.errors == [
        "Stock vigente insuficiente de P2: se pidieron 8 y hay 7",
        "Stock vigente insuficiente de P3: se pidieron 9 y hay 0",
    ]
    assert store.units() == {"L1": 50, "L2": 7, "L3": 20}
    assert store.sales["V1"].stock_aplicado is False


@pytest.mark.unit
def test_a_sale_discounts_its_stock_only_once():
    store = InMemoryStore([sale("V1", {"P1": 5})], [batch("L1", 50, date(2027, 1, 31))])
    run(store)

    with pytest.raises(BusinessRuleError, match="La venta V1 ya descontó su stock"):
        run(store)

    assert store.units() == {"L1": 45}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"estado": "Pendiente"}, "La venta V1 está 'Pendiente': solo una venta 'Completada'"),
        ({"estado": "Anulada"}, "La venta V1 está 'Anulada': solo una venta 'Completada'"),
        ({"activo": False}, "La venta V1 está dada de baja"),
    ],
)
def test_only_an_active_completed_sale_discounts_stock(changes, message):
    store = InMemoryStore([sale("V1", {"P1": 5}, **changes)], [batch("L1", 50, date(2027, 1, 31))])

    with pytest.raises(BusinessRuleError, match=message):
        run(store)

    assert store.units() == {"L1": 50}


@pytest.mark.unit
def test_unknown_sale_is_rejected():
    with pytest.raises(BusinessRuleError, match="La venta V9 no existe"):
        run(InMemoryStore([], []), "V9")


@pytest.mark.unit
def test_a_failure_after_the_discount_leaves_everything_as_it_was():
    store = InMemoryStore([sale("V1", {"P1": 5})], [batch("L1", 50, date(2027, 1, 31))])
    store.mark_stock_applied = lambda id_venta: False  # fails once the batch was discounted

    with pytest.raises(BusinessRuleError):
        run(store)

    assert store.units() == {"L1": 50}


# --- Against MongoDB --------------------------------------------------------------------


def register(database, id_venta: str, items: dict[str, int], id_sucursal: str = "S101") -> None:
    """Store a completed sale whose stock is still to be discounted."""
    database.ventas.insert_one(to_document(sale(id_venta, items, id_sucursal)))


def units(database, *batch_ids: str) -> dict[str, int]:
    return {
        document["_id"]: document["unidades"]
        for document in database.lotes.find({"_id": {"$in": list(batch_ids)}})
    }


@pytest.mark.integration
def test_stock_is_discounted_first_expired_first_out(loaded_for_writing):
    # PRD103 at S101: L104 (25, expired), L102 (30, 2027-06-03) and L103 (80, 2028-03-29).
    # PRD101 at S101: L117 (500, expires first but logically deleted) and L101 (120).
    register(loaded_for_writing, "V900", {"PRD103": 40, "PRD101": 1})

    result = update_stock(MongoUnitOfWork(loaded_for_writing), CLOCK, "V900")

    moved = [(m["id_lote"], m["unidades_antes"], m["descontado"]) for m in result["movimientos"]]
    assert moved == [("L101", 120, 1), ("L102", 30, 30), ("L103", 80, 10)]
    assert units(loaded_for_writing, "L101", "L102", "L103", "L104", "L117") == {
        "L101": 119,
        "L102": 0,
        "L103": 70,
        "L104": 25,
        "L117": 500,
    }
    assert loaded_for_writing.ventas.find_one({"_id": "V900"})["stock_aplicado"] is True


@pytest.mark.integration
def test_stock_of_other_branches_is_not_used(loaded_for_writing):
    # The wholesaler S109 has 2000 units of PRD101, but the sale is of S102, which has none.
    register(loaded_for_writing, "V900", {"PRD101": 1}, id_sucursal="S102")

    with pytest.raises(BusinessRuleError, match="insuficiente de PRD101: se pidieron 1 y hay 0"):
        update_stock(MongoUnitOfWork(loaded_for_writing), CLOCK, "V900")


@pytest.mark.integration
def test_insufficient_stock_rejects_the_whole_operation(loaded_for_writing):
    # PRD101 is covered; PRD103 has 110 non-expired units at S101.
    register(loaded_for_writing, "V900", {"PRD101": 5, "PRD103": 111})

    with pytest.raises(BusinessRuleError, match="de PRD103: se pidieron 111 y hay 110"):
        update_stock(MongoUnitOfWork(loaded_for_writing), CLOCK, "V900")

    assert units(loaded_for_writing, "L101", "L102", "L103") == {
        "L101": 120,
        "L102": 30,
        "L103": 80,
    }
    assert loaded_for_writing.ventas.find_one({"_id": "V900"})["stock_aplicado"] is False


@pytest.mark.integration
def test_a_failure_before_the_commit_rolls_the_batches_back(loaded_for_writing, monkeypatch):
    register(loaded_for_writing, "V900", {"PRD103": 40})

    def fail(self, id_venta):
        raise RuntimeError("failure after the batches were discounted")

    monkeypatch.setattr(MongoStore, "mark_stock_applied", fail)

    with pytest.raises(RuntimeError):
        update_stock(MongoUnitOfWork(loaded_for_writing), CLOCK, "V900")

    assert units(loaded_for_writing, "L102", "L103") == {"L102": 30, "L103": 80}


@pytest.mark.integration
@pytest.mark.parametrize(
    ("id_venta", "message"),
    [
        ("V102", "La venta V102 ya descontó su stock"),  # loaded as completed
        ("V011", "La venta V011 está 'Pendiente'"),
        ("V015", "La venta V015 está 'Anulada'"),
        ("V117", "La venta V117 está dada de baja"),
        ("V999", "La venta V999 no existe"),
    ],
)
def test_sales_that_cannot_discount_stock_are_rejected(loaded_for_writing, id_venta, message):
    before = list(loaded_for_writing.lotes.find().sort("_id"))

    with pytest.raises(BusinessRuleError, match=message):
        update_stock(MongoUnitOfWork(loaded_for_writing), CLOCK, id_venta)

    assert list(loaded_for_writing.lotes.find().sort("_id")) == before


@pytest.mark.integration
def test_concurrent_sales_never_leave_negative_stock(loaded_for_writing):
    # L112 is the only batch of PRD109 at S104 and has 3 units; 8 sales want one each.
    sales = [f"V9{n:02d}" for n in range(1, 9)]
    for id_venta in sales:
        register(loaded_for_writing, id_venta, {"PRD109": 1}, id_sucursal="S104")

    def discount(id_venta: str) -> bool:
        try:
            update_stock(MongoUnitOfWork(loaded_for_writing), CLOCK, id_venta)
        except BusinessRuleError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(discount, sales))

    assert outcomes.count(True) == 3
    assert units(loaded_for_writing, "L112") == {"L112": 0}
    applied = {"_id": {"$in": sales}, "stock_aplicado": True}
    assert loaded_for_writing.ventas.count_documents(applied) == 3


@pytest.mark.integration
def test_command_line_takes_the_sale_as_argument(loaded_for_writing, capsys, monkeypatch):
    monkeypatch.setenv("FARMARED_TODAY", TODAY.isoformat())
    get_settings.cache_clear()
    register(loaded_for_writing, "V900", {"PRD103": 40})

    assert main(["q15", "V900"]) == 0
    assert "q15 - Descuento de stock de la venta V900" in capsys.readouterr().out

    assert main(["q15", "V900"]) == 1
    assert "La venta V900 ya descontó su stock" in capsys.readouterr().out
