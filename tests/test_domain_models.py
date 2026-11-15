"""Entities reject records that break a single-record rule, and accept the course datasets."""

import csv
from pathlib import Path

import pytest
from pydantic import ValidationError

from farmared.domain.models import Batch, Customer, Prescription, Sale

pytestmark = pytest.mark.unit

GIVEN = Path(__file__).resolve().parents[1] / "data" / "given"


def rows(name: str) -> list[dict]:
    """Rows of a course CSV, with empty cells as None (the datasets' convention for nulls)."""
    with open(GIVEN / f"{name}.csv", encoding="utf-8", newline="") as file:
        return [
            {k: (v if v != "" else None) for k, v in row.items()} for row in csv.DictReader(file)
        ]


def test_entities_are_active_unless_stated():
    # recetas, ventas and stock_lotes come without the column: they load as active.
    assert Batch.model_validate(rows("stock_lotes")[0]).activo is True
    assert Customer.model_validate(rows("clientes")[7]).activo is False  # C008, logical delete


CUSTOMER = {
    "id_cliente": "C900",
    "nombre": "Ana",
    "apellido": "Gil",
    "dni": "30111222",
    "obra_social": "OSDE",
    "nro_afiliado": "OS-1",
}


@pytest.mark.parametrize(
    "changes",
    [
        {"obra_social": "Sin cobertura"},  # no insurance but a member number
        {"nro_afiliado": None},  # insurance without member number
        {"obra_social": "Medifé"},  # not an allowed value
        {"dni": "30.111.222"},
    ],
)
def test_customer_rejects_invalid_data(changes):
    with pytest.raises(ValidationError):
        Customer.model_validate({**CUSTOMER, **changes})


def test_batch_stock_cannot_be_negative():
    with pytest.raises(ValidationError):
        Batch.model_validate({**rows("stock_lotes")[0], "unidades": -1})


LONG_TERM = {  # RC004 of the course data
    "id_receta": "RC004",
    "id_cliente": "C006",
    "medico": "Dr. Pablo Echeverría",
    "matricula_medico": "MP-41203",
    "fecha_emision": "2026-09-20",
    "tipo": "Tratamiento prolongado",
    "dispensas_autorizadas": 3,
    "dispensas_realizadas": 1,
    "proxima_dispensa": "2026-10-20",
    "estado": "Vigente",
}


@pytest.mark.parametrize(
    "changes",
    [
        {"dispensas_realizadas": 4},  # more than authorised
        {"dispensas_autorizadas": 4},  # more than 3
        {"tipo": "Simple"},  # simple with 3 dispenses
        {"estado": "Completada"},  # completed with dispenses left
        {"dispensas_realizadas": 3},  # used up but still 'Vigente'
        {"proxima_dispensa": None},  # treatment in progress without next dispense
        {"dispensas_realizadas": 0},  # next dispense scheduled before the first one
    ],
)
def test_prescription_rejects_inconsistent_data(changes):
    with pytest.raises(ValidationError):
        Prescription.model_validate({**LONG_TERM, **changes})


SALE = {  # V002 of the course data
    "id_venta": "V002",
    "id_cliente": "C005",
    "id_farmaceutico": "F005",
    "id_sucursal": "S003",
    "id_receta": None,
    "fecha": "2025-06-24",
    "tipo": "Venta libre",
    "medio_pago": "Débito",
    "total": 5750,
    "estado": "Completada",
    "items": [
        {"id_detalle": "D002", "id_producto": "PRD011", "cantidad": 2, "precio_unit": 1750},
        {"id_detalle": "D003", "id_producto": "PRD001", "cantidad": 1, "precio_unit": 2250},
    ],
}


@pytest.mark.parametrize(
    "changes",
    [
        {"total": 5000},  # does not match the items
        {"items": []},
        {"tipo": "Con receta"},  # 'Con receta' without prescription
        {"id_receta": "RC001"},  # 'Venta libre' with prescription
        {"estado": "Pendiente", "stock_aplicado": True},  # only completed sales discount stock
        {"medio_pago": "Cheque"},
    ],
)
def test_sale_rejects_inconsistent_data(changes):
    with pytest.raises(ValidationError):
        Sale.model_validate({**SALE, **changes})


def test_sale_item_needs_positive_quantity_and_price():
    item = SALE["items"][0]
    for changes in ({"cantidad": 0}, {"precio_unit": 0}):
        with pytest.raises(ValidationError):
            Sale.model_validate({**SALE, "items": [{**item, **changes}]})
