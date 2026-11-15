"""q08 - Batches with fewer than 50 units, with their product, branch and supplier."""

from datetime import datetime

import pytest

from farmared.cli import main
from farmared.services.q08_low_stock_batches import low_stock_batches

pytestmark = pytest.mark.integration


def test_lists_the_batches_below_50_units_from_the_lowest(loaded):
    result = low_stock_batches(loaded)

    assert [(row["id_lote"], row["unidades"]) for row in result] == [
        ("L115", 0),
        ("L116", 2),
        ("L112", 3),
        ("L109", 5),
        ("L010", 12),
        ("L105", 12),
        ("L018", 15),
        ("L003", 18),
        ("L111", 18),
        ("L007", 22),
        ("L104", 25),
        ("L012", 30),
        ("L102", 30),
        ("L002", 35),
        ("L005", 40),
        ("L107", 40),
        ("L014", 45),
        ("L011", 48),
    ]


def test_each_batch_shows_product_branch_and_supplier(loaded):
    batch = next(row for row in low_stock_batches(loaded) if row["id_lote"] == "L010")

    assert batch == {
        "id_lote": "L010",
        "nro_lote": "L-2507P",
        "unidades": 12,
        "vencimiento": datetime(2027, 1, 31),
        "producto": {"id_producto": "PRD008", "nombre": "Alprazolam 0,5mg x30"},
        "sucursal": {
            "id_sucursal": "S003",
            "nombre": "Farmacia Rosario Centro",
            "tipo": "Farmacia",
        },
        "proveedor": {
            "id_proveedor": "PRV004",
            "razon_social": "Distribuidora Sur Salud S.A.",
        },
    }


def test_batches_with_50_units_or_more_are_left_out(loaded):
    ids = {row["id_lote"] for row in low_stock_batches(loaded)}

    assert not ids & {"L009", "L001", "L016", "L113"}  # 60, 120, 4000 and 2000 units


def test_logically_deleted_batches_are_left_out(loaded):
    assert "L117" not in {row["id_lote"] for row in low_stock_batches(loaded, below=1000)}


def test_expired_batches_and_inactive_products_are_still_reported(loaded):
    rows = {row["id_lote"]: row for row in low_stock_batches(loaded)}

    # L018: expired on 2026-09-30, of PRD012, a discontinued product.
    assert rows["L018"]["producto"]["id_producto"] == "PRD012"
    assert rows["L018"]["vencimiento"] == datetime(2026, 9, 30)


def test_the_limit_is_a_parameter(loaded):
    assert [row["id_lote"] for row in low_stock_batches(loaded, below=5)] == [
        "L115",
        "L116",
        "L112",
    ]


def test_command_line_prints_the_result(loaded, capsys):
    assert main(["q08", "--below", "5"]) == 0
    assert "q08 - Lotes con menos de 5 unidades" in capsys.readouterr().out
