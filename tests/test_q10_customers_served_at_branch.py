"""q10 - Customers who were served at a given branch."""

import pytest

from farmared.cli import main
from farmared.domain.errors import BusinessRuleError
from farmared.services.q10_customers_served_at_branch import customers_served_at_branch

pytestmark = pytest.mark.integration


def customer_ids(result: dict) -> list[str]:
    return [row["id_cliente"] for row in result["clientes"]]


def test_lists_each_customer_of_the_branch_once(loaded):
    # S001 has seven sales, of only two customers.
    result = customers_served_at_branch(loaded, "S001")

    assert result["sucursal"] == {
        "id_sucursal": "S001",
        "nombre": "Farmacia Palermo",
        "tipo": "Farmacia",
    }
    assert result["clientes"] == [
        {
            "id_cliente": "C001",
            "nombre": "Lucía",
            "apellido": "Fernández",
            "dni": "31245678",
            "activo": True,
        },
        {
            "id_cliente": "C006",
            "nombre": "Ricardo",
            "apellido": "Paz",
            "dni": "14876543",
            "activo": True,
        },
    ]


def test_sales_of_an_inactive_pharmacist_count(loaded):
    # V001 (C004) was registered by F004, inactive today, of branch S002.
    assert customer_ids(customers_served_at_branch(loaded, "S002")) == ["C001", "C004"]


def test_the_same_customer_can_appear_in_several_branches(loaded):
    assert "C001" in customer_ids(customers_served_at_branch(loaded, "S001"))
    assert "C001" in customer_ids(customers_served_at_branch(loaded, "S002"))


def test_pending_sales_count(loaded):
    # The only sale of S104 is V106, pending.
    assert customer_ids(customers_served_at_branch(loaded, "S104")) == ["C108"]


def test_logically_deleted_sales_do_not_count(loaded):
    # C105 only has V117 at S101, which is logically deleted.
    assert customer_ids(customers_served_at_branch(loaded, "S101")) == [
        "C101",
        "C102",
        "C103",
        "C109",
    ]


def test_branch_without_sales_has_no_customers(loaded):
    # S005 is the wholesaler: it does not register sales.
    assert customers_served_at_branch(loaded, "S005")["clientes"] == []


def test_unknown_branch_is_rejected(loaded):
    with pytest.raises(BusinessRuleError, match="La sucursal S999 no existe"):
        customers_served_at_branch(loaded, "S999")


def test_command_line_takes_the_branch_as_argument(loaded, capsys):
    assert main(["q10", "S002"]) == 0
    assert "q10 - Clientes atendidos en la sucursal S002" in capsys.readouterr().out

    assert main(["q10", "S999"]) == 1
    assert "La sucursal S999 no existe" in capsys.readouterr().out
