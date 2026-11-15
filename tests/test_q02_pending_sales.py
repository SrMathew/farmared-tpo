"""q02 - Sales in state 'Pendiente' with their assigned pharmacist and total."""

from datetime import datetime

import pytest

from farmared.cli import main
from farmared.services.q02_pending_sales import pending_sales

pytestmark = pytest.mark.integration


def test_lists_every_pending_sale_ordered_by_date(loaded):
    sales = pending_sales(loaded)

    # Two of the course (V011, V012) and two of the team (V106 today, V112 two days ago).
    assert [sale["id_venta"] for sale in sales] == ["V012", "V011", "V112", "V106"]


def test_each_sale_shows_pharmacist_licence_branch_and_total(loaded):
    assert pending_sales(loaded)[0] == {
        "id_venta": "V012",
        "fecha": datetime(2026, 10, 11),
        "id_cliente": "C002",
        "total": 9200,
        "farmaceutico": {
            "id_farmaceutico": "F005",
            "nombre": "Natalia",
            "apellido": "Giménez",
            "matricula": "MN-18289",
        },
        "sucursal": {"id_sucursal": "S003", "nombre": "Farmacia Rosario Centro"},
    }


def test_logically_deleted_sales_are_left_out(loaded):
    loaded.ventas.update_one({"_id": "V106"}, {"$set": {"activo": False}})
    try:
        assert "V106" not in {sale["id_venta"] for sale in pending_sales(loaded)}
    finally:
        loaded.ventas.update_one({"_id": "V106"}, {"$set": {"activo": True}})


def test_command_line_prints_the_result(loaded, capsys):
    assert main(["q02"]) == 0

    output = capsys.readouterr().out
    assert "q02 - Ventas pendientes con su farmacéutico" in output
    assert '"fecha": "2026-10-11"' in output
