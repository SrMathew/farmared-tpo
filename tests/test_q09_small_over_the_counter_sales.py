"""q09 - Sales of type 'Venta libre' with a total under $5,000, cancelled ones excluded."""

from datetime import datetime

import pytest

from farmared.cli import main
from farmared.services.q09_small_over_the_counter_sales import small_over_the_counter_sales

pytestmark = pytest.mark.integration


def test_lists_small_over_the_counter_sales_by_date(loaded):
    result = small_over_the_counter_sales(loaded)

    # Left out: V015 and V110 (cancelled), V117 (logically deleted), V001 (with
    # prescription) and V002 (5750). V112 is pending and is listed.
    assert [(row["id_venta"], row["total"]) for row in result] == [
        ("V108", 3200),  # more than a year before the load
        ("V013", 4400),
        ("V014", 4600),
        ("V104", 3200),
        ("V112", 3200),
    ]


def test_each_sale_comes_with_its_items(loaded):
    sale = next(row for row in small_over_the_counter_sales(loaded) if row["id_venta"] == "V014")

    assert sale == {
        "id_venta": "V014",
        "fecha": datetime(2026, 10, 5),
        "estado": "Completada",
        "total": 4600,
        "medio_pago": "Efectivo",
        "id_cliente": "C005",
        "id_farmaceutico": "F005",
        "id_sucursal": "S003",
        "items": [
            {"id_detalle": "D018", "id_producto": "PRD001", "cantidad": 1, "precio_unit": 2800},
            {"id_detalle": "D019", "id_producto": "PRD012", "cantidad": 1, "precio_unit": 1800},
        ],
    }


def test_the_limit_is_strict_and_is_a_parameter(loaded):
    # V013 has a total of exactly 4400.
    assert "V013" not in {
        row["id_venta"] for row in small_over_the_counter_sales(loaded, below=4400)
    }
    assert "V013" in {row["id_venta"] for row in small_over_the_counter_sales(loaded, below=4401)}


def test_command_line_prints_the_result(loaded, capsys):
    assert main(["q09"]) == 0
    assert "q09 - Ventas libres con total menor a $5000" in capsys.readouterr().out
