"""Entities are stored as documents and read back unchanged."""

from datetime import date, datetime

import pytest

from farmared.adapters.mongo.documents import collection_of, from_document, to_document
from farmared.adapters.mongo.ids import Sequence, format_id, number_of
from farmared.domain.models import Batch, Sale, SaleItem

pytestmark = pytest.mark.unit

BATCH = Batch(
    id_lote="L005",
    id_producto="PRD003",
    id_sucursal="S001",
    nro_lote="L-2506A",
    unidades=40,
    vencimiento=date(2026, 11, 30),
)

SALE = Sale(
    id_venta="V003",
    id_cliente="C001",
    id_farmaceutico="F001",
    id_sucursal="S001",
    id_receta="RC001",
    fecha=date(2026, 9, 10),
    tipo="Con receta",
    medio_pago="Obra social",
    total=9800,
    estado="Completada",
    stock_aplicado=True,
    items=[SaleItem(id_detalle="D004", id_producto="PRD003", cantidad=1, precio_unit=9800)],
)


def test_business_identifier_becomes_the_document_id():
    document = to_document(BATCH)

    assert document["_id"] == "L005"
    assert "id_lote" not in document


def test_dates_are_stored_as_midnight_and_logical_delete_flag_is_kept():
    document = to_document(BATCH)

    assert document["vencimiento"] == datetime(2026, 11, 30)
    assert document["activo"] is True


def test_sale_items_are_embedded_in_the_sale_document():
    document = to_document(SALE)

    assert document["items"] == [
        {"id_detalle": "D004", "id_producto": "PRD003", "cantidad": 1, "precio_unit": 9800}
    ]
    assert document["estado"] == "Completada"


@pytest.mark.parametrize("entity", [BATCH, SALE])
def test_document_round_trip_gives_back_the_same_entity(entity):
    assert from_document(type(entity), to_document(entity)) == entity


def test_each_entity_has_its_collection():
    assert collection_of(Batch) == "lotes"
    assert collection_of(Sale) == "ventas"


def test_identifier_format():
    assert format_id(Sequence.SALE, 17) == "V017"
    assert format_id(Sequence.PRODUCT, 5) == "PRD005"
    assert number_of(Sequence.PRESCRIPTION, "RC009") == 9
