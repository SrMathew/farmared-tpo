"""q06 - Valid long-term treatments whose next dispense is overdue, with the customer data."""

from datetime import date, datetime

import pytest

from farmared.cli import main
from farmared.clock import FixedClock
from farmared.services.q06_overdue_long_term_prescriptions import (
    overdue_long_term_prescriptions,
)

pytestmark = pytest.mark.integration

TODAY = date(2026, 11, 15)  # the day the test data is loaded with (see conftest)


def overdue(loaded, day: date = TODAY) -> list[dict]:
    return overdue_long_term_prescriptions(loaded, FixedClock(day))["recetas"]


def test_lists_overdue_treatments_from_the_most_overdue(loaded):
    result = overdue(loaded)

    assert [(row["id_receta"], row["dias_de_atraso"]) for row in result] == [
        ("RC002", 61),  # due 2026-09-15
        ("RC003", 45),  # due 2026-10-01
        ("RC004", 26),  # due 2026-10-20
        ("RC101", 5),  # due five days before the load
    ]


def test_each_prescription_carries_all_the_customer_data(loaded):
    assert overdue(loaded)[0] == {
        "id_receta": "RC002",
        "medico": "Dra. Silvia Montenegro",
        "fecha_emision": datetime(2026, 7, 15),
        "dispensas_autorizadas": 3,
        "dispensas_realizadas": 2,
        "proxima_dispensa": datetime(2026, 9, 15),
        "dias_de_atraso": 61,
        "cliente": {
            "id_cliente": "C003",
            "nombre": "Carla",
            "apellido": "Ruiz",
            "dni": "40123456",
            "email": "carla.r@gmail.com",
            "telefono": "3515334455",
            "ciudad": "Córdoba",
            "provincia": "Córdoba",
            "obra_social": "PAMI",
            "nro_afiliado": "PA-771203",
            "activo": True,
        },
    }


def test_treatments_not_yet_due_are_left_out(loaded):
    # RC106: next dispense ten days after the load.
    assert "RC106" not in {row["id_receta"] for row in overdue(loaded)}


def test_only_valid_long_term_treatments_are_listed(loaded):
    ids = {row["id_receta"] for row in overdue(loaded)}

    assert "RC103" not in ids  # long-term but completed
    assert "RC009" not in ids and "RC104" not in ids  # simple and expired
    assert "RC107" not in ids  # long-term, valid, never dispensed: nothing scheduled


def test_a_dispense_due_today_is_not_overdue_yet(loaded):
    # RC002 is due on 2026-09-15: "before today" is strict.
    assert overdue(loaded, date(2026, 9, 15)) == []
    assert [row["id_receta"] for row in overdue(loaded, date(2026, 9, 16))] == ["RC002"]


def test_result_reports_the_date_used(loaded):
    assert overdue_long_term_prescriptions(loaded, FixedClock(TODAY))["hoy"] == TODAY


def test_command_line_prints_the_result(loaded, capsys):
    assert main(["q06"]) == 0
    assert "q06 - Tratamientos prolongados con dispensa atrasada" in capsys.readouterr().out
