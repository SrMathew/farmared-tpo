"""q05 - Active pharmacists and the number of sales they registered in the last 60 days."""

from datetime import date

import pytest

from farmared.cli import main
from farmared.clock import FixedClock
from farmared.services.q05_pharmacist_sales_last_60_days import pharmacist_sales_last_60_days

pytestmark = pytest.mark.integration

TODAY = date(2026, 11, 15)  # the day the test data is loaded with (see conftest)


def counts(result: dict) -> dict[str, int]:
    return {row["id_farmaceutico"]: row["cantidad_ventas"] for row in result["farmaceuticos"]}


def test_period_is_the_60_days_before_the_system_date(loaded):
    result = pharmacist_sales_last_60_days(loaded, FixedClock(TODAY))

    assert (result["desde"], result["hasta"]) == (date(2026, 9, 16), date(2026, 11, 15))


def test_counts_the_sales_of_each_active_pharmacist(loaded):
    result = pharmacist_sales_last_60_days(loaded, FixedClock(TODAY))

    assert counts(result) == {
        "F101": 4,
        "F005": 3,
        "F002": 2,
        "F104": 2,
        "F001": 1,
        "F003": 1,
        "F006": 1,
        "F102": 1,
        "F103": 1,
        "F105": 1,
        "F106": 1,
        "F007": 0,
        "F107": 0,
        "F109": 0,
        "F110": 0,
    }


def test_result_is_ordered_by_number_of_sales(loaded):
    rows = pharmacist_sales_last_60_days(loaded, FixedClock(TODAY))["farmaceuticos"]

    assert [row["id_farmaceutico"] for row in rows][:4] == ["F101", "F005", "F002", "F104"]
    assert rows[0] == {
        "id_farmaceutico": "F101",
        "nombre": "Mariana",
        "apellido": "Paredes",
        "matricula": "MP-40101",
        "id_sucursal": "S101",
        "cantidad_ventas": 4,
    }


def test_pharmacists_without_sales_appear_with_zero(loaded):
    result = counts(pharmacist_sales_last_60_days(loaded, FixedClock(TODAY)))

    assert result["F007"] == 0  # works at the warehouse, which registers no sales


def test_inactive_pharmacists_are_left_out(loaded):
    result = counts(pharmacist_sales_last_60_days(loaded, FixedClock(TODAY)))

    assert "F004" not in result and "F108" not in result


def test_cancelled_and_logically_deleted_sales_do_not_count(loaded):
    result = counts(pharmacist_sales_last_60_days(loaded, FixedClock(TODAY)))

    # F002: V008 and V016 count; V015 (cancelled, 2026-09-25) does not.
    assert result["F002"] == 2
    # F101: V117 (2026-11-07) is logically deleted.
    assert result["F101"] == 4


def test_pending_sales_count(loaded):
    # F006 only has V011, pending.
    assert counts(pharmacist_sales_last_60_days(loaded, FixedClock(TODAY)))["F006"] == 1


def test_the_period_moves_with_the_date(loaded):
    # 60 days later, the course sales of September and October are out of the period.
    later = counts(pharmacist_sales_last_60_days(loaded, FixedClock(date(2027, 1, 10))))

    assert later["F005"] == 0
    assert later["F101"] == 1  # only V111, of 2026-11-15


def test_command_line_prints_the_result(loaded, capsys):
    assert main(["q05"]) == 0
    assert "q05 - Ventas por farmacéutico activo" in capsys.readouterr().out
