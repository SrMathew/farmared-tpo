"""q11 - Aggregated view: total income per pharmacist in the current month."""

from datetime import date

import pytest

from farmared.adapters.mongo import queries
from farmared.cli import main
from farmared.clock import FixedClock, SystemClock
from farmared.config import get_settings
from farmared.services.q11_pharmacist_income_current_month import (
    pharmacist_income_current_month,
)

pytestmark = pytest.mark.integration

TODAY = date(2026, 11, 15)  # the day the test data is loaded with (see conftest)


def income(result: dict) -> list[tuple[str, int]]:
    return [(row["id_farmaceutico"], row["ingresos"]) for row in result["farmaceuticos"]]


def test_adds_the_completed_sales_of_the_month_per_pharmacist(loaded):
    result = pharmacist_income_current_month(loaded, FixedClock(TODAY))

    assert result["mes"] == "2026-11"
    assert result["farmaceuticos"] == [
        {
            "id_farmaceutico": "F101",
            "nombre": "Mariana",
            "apellido": "Paredes",
            "matricula": "MP-40101",
            "ingresos": 24100,  # V104 + V111
        },
        {
            "id_farmaceutico": "F103",
            "nombre": "Julieta",
            "apellido": "Campos",
            "matricula": "MP-40103",
            "ingresos": 14500,
        },
        {
            "id_farmaceutico": "F102",
            "nombre": "Ezequiel",
            "apellido": "Ortiz",
            "matricula": "MP-40102",
            "ingresos": 11000,
        },
    ]


def test_pending_and_cancelled_sales_compute_no_income(loaded):
    result = dict(income(pharmacist_income_current_month(loaded, FixedClock(TODAY))))

    assert "F105" not in result and "F106" not in result  # V106 and V112, pending
    assert result["F102"] == 11000  # V110 (3900) is cancelled


def test_logically_deleted_sales_compute_no_income(loaded):
    result = dict(income(pharmacist_income_current_month(loaded, FixedClock(TODAY))))

    assert result["F101"] == 24100  # without V117 (3900), deleted


def test_the_month_changes_with_the_date(loaded):
    # The last day of October: V107 (that day) counts, the sales of November do not.
    result = pharmacist_income_current_month(loaded, FixedClock(date(2026, 10, 31)))

    assert result["mes"] == "2026-10"
    assert income(result) == [
        ("F101", 19600),  # V101 + V107
        ("F104", 9900),
        ("F002", 7800),
        ("F003", 7100),
        ("F005", 4600),
        ("F001", 4400),
    ]


def test_the_first_day_belongs_to_its_month(loaded):
    first = pharmacist_income_current_month(loaded, FixedClock(date(2026, 11, 1)))

    assert income(first) == income(pharmacist_income_current_month(loaded, FixedClock(TODAY)))


def test_the_view_gives_the_income_of_the_month_of_the_system_date(loaded):
    # The view decides the month with the clock of the engine, so the expected result is
    # the same statement run with the real date.
    clock = SystemClock(get_settings().timezone)

    assert queries.MONTHLY_INCOME_VIEW in loaded.list_collection_names()
    assert pharmacist_income_current_month(loaded, clock)[
        "farmaceuticos"
    ] == queries.pharmacist_income_in_month_of(loaded, clock.today())


def test_command_line_prints_the_result(loaded, capsys):
    assert main(["q11"]) == 0
    assert "q11 - Ingresos por farmacéutico en el mes actual" in capsys.readouterr().out
