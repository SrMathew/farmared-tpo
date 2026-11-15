"""q03 - Complete history of a customer: sales and prescriptions in chronological order."""

from datetime import datetime

import pytest

from farmared.cli import main
from farmared.domain.errors import BusinessRuleError
from farmared.services.q03_customer_history import customer_history

pytestmark = pytest.mark.integration


def timeline(history: dict) -> list[tuple[str, str]]:
    return [(entry["fecha"].date().isoformat(), entry["id"]) for entry in history["historial"]]


def test_sales_and_prescriptions_come_in_chronological_order(loaded):
    # C006 of the course data: a long-term treatment and its dispenses.
    assert timeline(customer_history(loaded, "C006")) == [
        ("2026-08-01", "RC003"),  # same day: the prescription before its sale
        ("2026-08-01", "V006"),
        ("2026-09-01", "V007"),
        ("2026-09-20", "RC004"),
        ("2026-09-20", "V008"),
        ("2026-10-07", "V016"),
    ]


def test_history_identifies_the_customer(loaded):
    assert customer_history(loaded, "C006")["cliente"] == {
        "id_cliente": "C006",
        "nombre": "Ricardo",
        "apellido": "Paz",
        "activo": True,
    }


def test_sale_entry_carries_its_embedded_items(loaded):
    sale = customer_history(loaded, "C006")["historial"][1]

    assert sale == {
        "fecha": datetime(2026, 8, 1),
        "registro": "venta",
        "id": "V006",
        "tipo": "Con receta",
        "estado": "Completada",
        "medio_pago": "Obra social",
        "total": 22100,
        "id_farmaceutico": "F002",
        "id_receta": "RC003",
        "items": [
            {"id_detalle": "D007", "id_producto": "PRD005", "cantidad": 3, "precio_unit": 5400},
            {"id_detalle": "D008", "id_producto": "PRD009", "cantidad": 1, "precio_unit": 5900},
        ],
    }


def test_prescription_entry_carries_its_dispenses(loaded):
    prescription = customer_history(loaded, "C006")["historial"][0]

    assert prescription == {
        "fecha": datetime(2026, 8, 1),
        "registro": "receta",
        "id": "RC003",
        "tipo": "Tratamiento prolongado",
        "estado": "Vigente",
        "medico": "Dr. Pablo Echeverría",
        "dispensas_autorizadas": 3,
        "dispensas_realizadas": 2,
        "proxima_dispensa": datetime(2026, 10, 1),
    }


def test_logically_deleted_records_are_not_part_of_the_history(loaded):
    # C101 has the deleted prescription RC111; today is 2026-11-15 in the tests.
    assert timeline(customer_history(loaded, "C101")) == [
        ("2026-10-10", "RC101"),
        ("2026-10-11", "V101"),
        ("2026-11-12", "V102"),
        ("2026-11-13", "RC102"),
        ("2026-11-14", "RC110"),
        ("2026-11-15", "V111"),
    ]


def test_cancelled_sales_stay_in_the_history(loaded):
    history = customer_history(loaded, "C001")

    assert ("2026-09-25", "V015") in timeline(history)


def test_customer_without_activity_has_an_empty_history(loaded):
    assert customer_history(loaded, "C008")["historial"] == []


def test_unknown_customer_is_rejected(loaded):
    with pytest.raises(BusinessRuleError, match="El cliente C999 no existe"):
        customer_history(loaded, "C999")


def test_command_line_takes_the_customer_as_argument(loaded, capsys):
    assert main(["q03", "C006"]) == 0
    assert "q03 - Historial del cliente C006" in capsys.readouterr().out

    assert main(["q03", "C999"]) == 1
    assert "El cliente C999 no existe" in capsys.readouterr().out
