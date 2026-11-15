"""Business rules of section 2.11."""

from datetime import date

import pytest

from farmared.domain.errors import InsufficientStockError
from farmared.domain.models import (
    Batch,
    Branch,
    Customer,
    Pharmacist,
    Prescription,
    Product,
    Sale,
    SaleItem,
)
from farmared.domain.rules import (
    allocate_fefo,
    dispense_errors,
    has_economic_effect,
    inactive_errors,
    is_expired,
    prescription_after_dispense,
    prescription_errors,
    requires_prescription,
    sale_total,
    selling_point_errors,
)

pytestmark = pytest.mark.unit

TODAY = date(2026, 10, 13)


def product(id_producto="PRD001", condicion_venta="Venta libre", activo=True) -> Product:
    return Product(
        id_producto=id_producto,
        nombre="Producto",
        principio_activo="Droga",
        categoria="Categoría",
        presentacion="Comprimidos",
        condicion_venta=condicion_venta,
        precio_unit=1000,
        id_proveedor="PRV001",
        activo=activo,
    )


def prescription(**changes) -> Prescription:
    data = {
        "id_receta": "RC900",
        "id_cliente": "C001",
        "medico": "Dra. Ejemplo",
        "matricula_medico": "MP-1",
        "fecha_emision": date(2026, 10, 1),
        "tipo": "Simple",
        "dispensas_autorizadas": 1,
        "dispensas_realizadas": 0,
        "proxima_dispensa": None,
        "estado": "Vigente",
    }
    return Prescription.model_validate({**data, **changes})


def batch(id_lote, unidades, vencimiento, activo=True) -> Batch:
    return Batch(
        id_lote=id_lote,
        id_producto="PRD001",
        id_sucursal="S001",
        nro_lote=f"N-{id_lote}",
        unidades=unidades,
        vencimiento=vencimiento,
        activo=activo,
    )


# --- Sale condition ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("condicion_venta", "expected"),
    [("Venta libre", False), ("Bajo receta", True), ("Bajo receta archivada", True)],
)
def test_which_products_require_prescription(condicion_venta, expected):
    assert requires_prescription(product(condicion_venta=condicion_venta)) is expected


def test_over_the_counter_products_need_no_prescription():
    assert prescription_errors(None, "C001", [product()], TODAY) == []


def test_product_under_prescription_without_prescription_is_rejected():
    errors = prescription_errors(None, "C001", [product("PRD003", "Bajo receta")], TODAY)

    assert errors == ["Los productos ['PRD003'] son de venta bajo receta y no se indicó receta"]


def test_prescription_of_the_same_customer_is_accepted():
    products = [product("PRD003", "Bajo receta"), product()]

    assert prescription_errors(prescription(), "C001", products, TODAY) == []


def test_prescription_of_another_customer_is_rejected():
    errors = prescription_errors(prescription(), "C002", [product("PRD003", "Bajo receta")], TODAY)

    assert errors == ["La receta RC900 pertenece a otro cliente (C001)"]


def test_prescription_issued_after_the_sale_is_rejected():
    errors = prescription_errors(
        prescription(), "C001", [product("PRD003", "Bajo receta")], date(2026, 9, 30)
    )

    assert errors == ["La receta RC900 fue emitida después de la fecha de la venta"]


def test_only_a_valid_prescription_can_be_dispensed():
    assert dispense_errors(prescription()) == []
    assert dispense_errors(prescription(estado="Vencida")) == ["La receta RC900 está 'Vencida'"]
    assert dispense_errors(prescription(dispensas_realizadas=1, estado="Completada")) == [
        "La receta RC900 está 'Completada'"
    ]


# --- Long-term treatment ----------------------------------------------------------------


def test_simple_prescription_is_completed_by_its_only_dispense():
    after = prescription_after_dispense(prescription(), TODAY)

    assert (after.dispensas_realizadas, after.estado, after.proxima_dispensa) == (
        1,
        "Completada",
        None,
    )


def test_filed_prescription_is_completed_by_its_only_dispense():
    after = prescription_after_dispense(prescription(tipo="Archivada"), TODAY)

    assert (after.dispensas_realizadas, after.estado) == (1, "Completada")


def test_long_term_treatment_schedules_the_next_dispense_30_days_later():
    treatment = prescription(tipo="Tratamiento prolongado", dispensas_autorizadas=3)

    first = prescription_after_dispense(treatment, date(2026, 10, 13))
    second = prescription_after_dispense(first, date(2026, 11, 12))

    assert (first.dispensas_realizadas, first.estado, first.proxima_dispensa) == (
        1,
        "Vigente",
        date(2026, 11, 12),
    )
    assert (second.dispensas_realizadas, second.estado, second.proxima_dispensa) == (
        2,
        "Vigente",
        date(2026, 12, 12),
    )


def test_long_term_treatment_is_completed_by_its_last_dispense():
    treatment = prescription(
        tipo="Tratamiento prolongado",
        dispensas_autorizadas=3,
        dispensas_realizadas=2,
        proxima_dispensa=date(2026, 10, 1),
    )

    after = prescription_after_dispense(treatment, TODAY)

    assert (after.dispensas_realizadas, after.estado, after.proxima_dispensa) == (
        3,
        "Completada",
        None,
    )


def test_dispensing_does_not_modify_the_original_prescription():
    original = prescription()

    prescription_after_dispense(original, TODAY)

    assert original.dispensas_realizadas == 0


# --- Sale status, branches and prices ---------------------------------------------------


@pytest.mark.parametrize(
    ("estado", "expected"), [("Completada", True), ("Pendiente", False), ("Anulada", False)]
)
def test_only_completed_sales_have_economic_effect(estado, expected):
    sale = Sale(
        id_venta="V900",
        id_cliente="C001",
        id_farmaceutico="F001",
        id_sucursal="S001",
        fecha=TODAY,
        tipo="Venta libre",
        medio_pago="Efectivo",
        total=2000,
        estado=estado,
        items=[SaleItem(id_detalle="D900", id_producto="PRD001", cantidad=2, precio_unit=1000)],
    )

    assert has_economic_effect(sale) is expected


def pharmacist(activo=True) -> Pharmacist:
    return Pharmacist(
        id_farmaceutico="F001",
        nombre="Mariana",
        apellido="Quiroga",
        matricula="MN-18041",
        cargo="Director Técnico",
        id_sucursal="S001",
        activo=activo,
    )


def branch(tipo="Farmacia", activo=True) -> Branch:
    return Branch(id_sucursal="S001", nombre="Sucursal", tipo=tipo, activo=activo)


def customer(activo=True) -> Customer:
    return Customer(
        id_cliente="C001",
        nombre="Lucía",
        apellido="Fernández",
        dni="31245678",
        obra_social="Sin cobertura",
        activo=activo,
    )


def test_sales_are_only_registered_in_pharmacies():
    assert selling_point_errors(pharmacist(), branch("Farmacia")) == []
    assert selling_point_errors(pharmacist(), branch("Droguería")) == [
        "La sucursal S001 del farmacéutico F001 es de tipo 'Droguería': "
        "solo las farmacias registran ventas"
    ]


def test_everything_in_a_new_sale_has_to_be_active():
    assert inactive_errors(customer(), pharmacist(), branch(), [product()]) == []
    assert inactive_errors(
        customer(activo=False),
        pharmacist(activo=False),
        branch(activo=False),
        [product(activo=False)],
    ) == [
        "El cliente C001 está dado de baja",
        "El farmacéutico F001 está inactivo",
        "La sucursal S001 está inactiva",
        "El producto PRD001 está discontinuado",
    ]


def test_sale_total_is_the_sum_of_its_items():
    items = [
        SaleItem(id_detalle="D007", id_producto="PRD005", cantidad=3, precio_unit=5400),
        SaleItem(id_detalle="D008", id_producto="PRD009", cantidad=1, precio_unit=5900),
    ]

    assert sale_total(items) == 22100  # V006 of the course data


# --- Stock: FEFO, no expired batches, never negative -------------------------------------


def test_a_batch_expires_the_day_after_its_expiry_date():
    assert is_expired(batch("L1", 10, date(2026, 10, 12)), TODAY) is True
    assert is_expired(batch("L1", 10, TODAY), TODAY) is False


def test_fefo_consumes_the_batch_that_expires_first():
    batches = [
        batch("L015", 100, date(2027, 6, 30)),
        batch("L005", 40, date(2026, 11, 30)),
    ]

    assert allocate_fefo(batches, "PRD003", 10, TODAY) == [("L005", 10)]


def test_fefo_continues_with_the_next_batch_when_one_is_not_enough():
    batches = [
        batch("L015", 100, date(2027, 6, 30)),
        batch("L005", 40, date(2026, 11, 30)),
    ]

    assert allocate_fefo(batches, "PRD003", 50, TODAY) == [("L005", 40), ("L015", 10)]


def test_fefo_skips_expired_inactive_and_empty_batches():
    batches = [
        batch("L1", 30, date(2026, 9, 30)),  # expired
        batch("L2", 30, date(2026, 11, 30), activo=False),  # logically deleted
        batch("L3", 0, date(2026, 12, 31)),  # empty
        batch("L4", 30, date(2027, 1, 31)),
    ]

    assert allocate_fefo(batches, "PRD001", 5, TODAY) == [("L4", 5)]


def test_fefo_rejects_the_whole_request_when_stock_is_not_enough():
    batches = [
        batch("L1", 30, date(2026, 9, 30)),  # expired: does not count
        batch("L4", 30, date(2027, 1, 31)),
    ]

    with pytest.raises(InsufficientStockError) as raised:
        allocate_fefo(batches, "PRD001", 31, TODAY)

    assert (raised.value.requested, raised.value.available) == (31, 30)
    assert str(raised.value) == "Stock vigente insuficiente de PRD001: se pidieron 31 y hay 30"


def test_fefo_can_use_a_batch_completely():
    assert allocate_fefo([batch("L1", 5, date(2027, 1, 31))], "PRD001", 5, TODAY) == [("L1", 5)]
