"""q04 - Customers with more than one prescription on record, and how many."""

import pytest

from farmared.cli import main
from farmared.services.q04_customers_with_several_prescriptions import (
    customers_with_several_prescriptions,
)

pytestmark = pytest.mark.integration


def test_lists_customers_with_more_than_one_prescription_and_the_count(loaded):
    result = customers_with_several_prescriptions(loaded)

    # Highest count first, then by customer. Prescriptions count whatever their state
    # (C002: one completed and one expired); logically deleted ones do not (C101 has a
    # fourth one, RC111, deleted). Customers with a single prescription are left out.
    assert [(row["id_cliente"], row["cantidad_recetas"]) for row in result] == [
        ("C101", 3),
        ("C001", 2),
        ("C002", 2),
        ("C006", 2),
        ("C102", 2),
        ("C104", 2),
    ]


def test_each_row_identifies_the_customer(loaded):
    assert customers_with_several_prescriptions(loaded)[1] == {
        "id_cliente": "C001",
        "nombre": "Lucía",
        "apellido": "Fernández",
        "dni": "31245678",
        "cantidad_recetas": 2,
    }


def test_command_line_prints_the_result(loaded, capsys):
    assert main(["q04"]) == 0
    assert "q04 - Clientes con más de una receta" in capsys.readouterr().out
