"""q04 - Customers with more than one prescription on record, and how many."""

import pytest

from farmared.cli import main
from farmared.services.q04_customers_with_several_prescriptions import (
    customers_with_several_prescriptions,
)

pytestmark = pytest.mark.integration


def test_lists_customers_with_more_than_one_prescription_and_the_count(loaded):
    result = customers_with_several_prescriptions(loaded)

    # Highest count first, then by customer.
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


def test_customers_with_a_single_prescription_are_left_out(loaded):
    ids = {row["id_cliente"] for row in customers_with_several_prescriptions(loaded)}

    assert not ids & {"C003", "C004", "C007", "C103", "C108", "C109"}


def test_logically_deleted_prescriptions_do_not_count(loaded):
    # C101 has four prescriptions on file; RC111 is logically deleted.
    assert loaded.recetas.count_documents({"id_cliente": "C101"}) == 4
    assert customers_with_several_prescriptions(loaded)[0]["cantidad_recetas"] == 3


def test_prescriptions_count_whatever_their_state(loaded):
    # C002: RC005 is completed and RC009 expired.
    assert "C002" in {row["id_cliente"] for row in customers_with_several_prescriptions(loaded)}


def test_command_line_prints_the_result(loaded, capsys):
    assert main(["q04"]) == 0
    assert "q04 - Clientes con más de una receta" in capsys.readouterr().out
