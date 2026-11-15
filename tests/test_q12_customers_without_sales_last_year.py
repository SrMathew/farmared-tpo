"""q12 - Customers with no sale registered in the last year."""

from datetime import date

import pytest

from farmared.cli import main
from farmared.clock import FixedClock
from farmared.services.q12_customers_without_sales_last_year import (
    customers_without_sales_last_year,
)

pytestmark = pytest.mark.integration

TODAY = date(2026, 11, 15)  # the day the test data is loaded with (see conftest)


def customer_ids(result: dict) -> list[str]:
    return [row["id_cliente"] for row in result["clientes"]]


def test_period_is_the_year_before_the_system_date(loaded):
    result = customers_without_sales_last_year(loaded, FixedClock(TODAY))

    assert (result["desde"], result["hasta"]) == (date(2025, 11, 15), date(2026, 11, 15))


def test_lists_the_active_customers_without_sales_in_the_period(loaded):
    result = customers_without_sales_last_year(loaded, FixedClock(TODAY))

    # C106 never bought; the only sale of C105 in the period is logically deleted. C008 and
    # C110 have no sales either, but they are inactive.
    assert customer_ids(result) == ["C004", "C105", "C106", "C107"]
    assert result["clientes"][0] == {
        "id_cliente": "C004",
        "nombre": "Federico",
        "apellido": "Navarro",
        "dni": "33987654",
    }


def test_a_pending_sale_counts_and_a_cancelled_one_does_not(loaded):
    ids = customer_ids(customers_without_sales_last_year(loaded, FixedClock(TODAY)))
    assert "C108" not in ids  # only pending sales: V106 and V112

    # On 2027-11-06 the last sale of C103 within the year is V110, cancelled.
    later = customer_ids(customers_without_sales_last_year(loaded, FixedClock(date(2027, 11, 6))))
    assert "C103" in later


def test_a_sale_made_exactly_one_year_ago_still_counts(loaded):
    # The only sale of C107 is V108, of 2025-10-11.
    on_the_day = customers_without_sales_last_year(loaded, FixedClock(date(2026, 10, 11)))
    the_day_after = customers_without_sales_last_year(loaded, FixedClock(date(2026, 10, 12)))

    assert "C107" not in customer_ids(on_the_day)
    assert "C107" in customer_ids(the_day_after)


def test_command_line_prints_the_result(loaded, capsys):
    assert main(["q12"]) == 0
    assert "q12 - Clientes activos sin ventas en el último año" in capsys.readouterr().out
