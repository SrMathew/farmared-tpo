"""q14 - Registration of a new 'Completada' sale, with its prescription and its stock."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from fakes.sales import InMemoryIdempotencyKeys, InMemorySalesStore, RecordingRanking
from fakes.stock import InMemoryUnitOfWork

from farmared.adapters.mongo.documents import COUNTERS
from farmared.adapters.mongo.unit_of_work import MongoUnitOfWork
from farmared.adapters.redis.connection import get_redis
from farmared.adapters.redis.idempotency_keys import RedisIdempotencyKeys
from farmared.adapters.redis.product_ranking import ProductRanking
from farmared.cli import main
from farmared.clock import FixedClock
from farmared.config import get_settings
from farmared.domain.errors import BusinessRuleError
from farmared.domain.models import (
    Batch,
    Branch,
    Customer,
    Pharmacist,
    Prescription,
    Product,
)
from farmared.services.q14_register_sale import register_sale
from farmared.services.redis_sync import product_ranking_differences

TODAY = date(2026, 11, 15)  # the day the test data is loaded with (see conftest)
CLOCK = FixedClock(TODAY)


# --- A small world in memory ------------------------------------------------------------


def customer(id_cliente: str, activo: bool = True) -> Customer:
    return Customer(
        id_cliente=id_cliente,
        nombre="Ana",
        apellido="Gil",
        dni=id_cliente[1:],
        obra_social="Sin cobertura",
        activo=activo,
    )


def branch(id_sucursal: str, tipo: str = "Farmacia", activo: bool = True) -> Branch:
    return Branch(id_sucursal=id_sucursal, nombre=id_sucursal, tipo=tipo, activo=activo)


def pharmacist(id_farmaceutico: str, id_sucursal: str, activo: bool = True) -> Pharmacist:
    return Pharmacist(
        id_farmaceutico=id_farmaceutico,
        nombre="Leo",
        apellido="Paz",
        matricula=f"M-{id_farmaceutico}",
        cargo="Farmacéutico",
        id_sucursal=id_sucursal,
        activo=activo,
    )


def product(id_producto: str, condicion: str, precio: int, activo: bool = True) -> Product:
    return Product(
        id_producto=id_producto,
        nombre=id_producto,
        principio_activo="x",
        categoria="x",
        presentacion="x",
        condicion_venta=condicion,
        precio_unit=precio,
        id_proveedor="PRV1",
        activo=activo,
    )


def prescription(id_receta: str, id_cliente: str = "C1", **changes) -> Prescription:
    data = {
        "id_receta": id_receta,
        "id_cliente": id_cliente,
        "medico": "Dra. Sol",
        "matricula_medico": "MP-1",
        "fecha_emision": date(2026, 11, 1),
        "tipo": "Simple",
        "dispensas_autorizadas": 1,
        "dispensas_realizadas": 0,
        "estado": "Vigente",
    }
    return Prescription.model_validate(data | changes)


def batch(id_lote: str, id_producto: str, units: int) -> Batch:
    return Batch(
        id_lote=id_lote,
        id_producto=id_producto,
        id_sucursal="S1",
        nro_lote=f"N-{id_lote}",
        unidades=units,
        vencimiento=date(2027, 6, 30),
    )


LONG_TERM = {"tipo": "Tratamiento prolongado", "dispensas_autorizadas": 3}


@pytest.fixture
def store():
    return InMemorySalesStore(
        customers=[customer("C1"), customer("C2"), customer("C3", activo=False)],
        pharmacists=[
            pharmacist("F1", "S1"),
            pharmacist("F2", "S2"),  # works at the wholesaler
            pharmacist("F3", "S1", activo=False),
        ],
        branches=[branch("S1"), branch("S2", tipo="Droguería")],
        products=[
            product("P1", "Venta libre", 100),
            product("P2", "Bajo receta", 200),
            product("P4", "Venta libre", 400, activo=False),
        ],
        prescriptions=[
            prescription("R1"),
            prescription(
                "R2", **LONG_TERM, dispensas_realizadas=1, proxima_dispensa=date(2026, 11, 10)
            ),
            prescription("R4", estado="Vencida"),
            prescription("R5", id_cliente="C2"),
        ],
        batches=[batch("L1", "P1", 50), batch("L2", "P2", 5)],
    )


@pytest.fixture
def ranking():
    return RecordingRanking()


def register(store, ranking, items, id_receta=None, **changes) -> dict:
    arguments = {
        "id_cliente": "C1",
        "id_farmaceutico": "F1",
        "items": items,
        "medio_pago": "Efectivo",
        "id_receta": id_receta,
    }
    return register_sale(InMemoryUnitOfWork(store), ranking, CLOCK, **(arguments | changes))


def state(store) -> tuple:
    return (
        dict(store.sales),
        dict(store.prescriptions),
        store.units(),
        store.last_sale,
        store.last_item,
    )


# --- The rules, without database engines ------------------------------------------------


@pytest.mark.unit
def test_over_the_counter_sale_is_stored_completed_with_its_stock(store, ranking):
    result = register(store, ranking, [("P1", 3)])

    assert result["venta"] == {
        "activo": True,
        "id_venta": "V001",
        "id_cliente": "C1",
        "id_farmaceutico": "F1",
        "id_sucursal": "S1",  # the branch of the pharmacist
        "id_receta": None,
        "fecha": TODAY,
        "tipo": "Venta libre",
        "medio_pago": "Efectivo",
        "total": 300,
        "estado": "Completada",
        "items": [{"id_detalle": "D001", "id_producto": "P1", "cantidad": 3, "precio_unit": 100}],
        "stock_aplicado": True,
    }
    assert result["receta"] is None
    assert [(m["id_lote"], m["unidades_despues"]) for m in result["stock"]] == [("L1", 47)]
    assert store.sales["V001"].stock_aplicado is True
    assert store.units()["L1"] == 47


@pytest.mark.unit
def test_prices_come_from_the_catalogue_and_the_total_from_the_items(store, ranking):
    result = register(store, ranking, [("P1", 2), ("P2", 1)], id_receta="R1")

    assert [(i["id_detalle"], i["precio_unit"]) for i in result["venta"]["items"]] == [
        ("D001", 100),
        ("D002", 200),
    ]
    assert result["venta"]["total"] == 2 * 100 + 200
    assert result["venta"]["tipo"] == "Con receta"


@pytest.mark.unit
def test_simple_prescription_is_completed_by_its_only_dispense(store, ranking):
    result = register(store, ranking, [("P2", 1)], id_receta="R1")

    assert (result["receta"]["antes"]["estado"], result["receta"]["despues"]["estado"]) == (
        "Vigente",
        "Completada",
    )
    assert store.prescriptions["R1"].dispensas_realizadas == 1


@pytest.mark.unit
def test_long_term_treatment_schedules_the_next_dispense_30_days_later(store, ranking):
    after = register(store, ranking, [("P2", 1)], id_receta="R2")["receta"]["despues"]

    assert (after["dispensas_realizadas"], after["estado"], after["proxima_dispensa"]) == (
        2,
        "Vigente",
        date(2026, 12, 15),
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"id_cliente": "C9"}, "El cliente C9 no existe"),
        ({"id_farmaceutico": "F9"}, "El farmacéutico F9 no existe"),
        ({"id_farmaceutico": "F2"}, "solo las farmacias registran ventas"),
        ({"items": [("P9", 1)]}, "El producto P9 no existe"),
        ({"items": [("P2", 1)]}, "son de venta bajo receta y no se indicó receta"),
        ({"items": [("P2", 1)], "id_receta": "R9"}, "La receta R9 no existe"),
        ({"items": [("P2", 1)], "id_receta": "R5"}, "La receta R5 pertenece a otro cliente"),
        ({"items": [("P2", 1)], "id_receta": "R4"}, "La receta R4 está 'Vencida'"),
        ({"id_receta": "R1"}, "Ningún producto de la venta es de venta bajo receta"),
        ({"medio_pago": "Cheque"}, "Medio de pago no válido: Cheque"),
        ({"items": [("P1", 0)]}, "La cantidad de P1 debe ser un entero mayor a cero"),
        ({"items": []}, "La venta no tiene ítems"),
    ],
)
def test_a_rejected_sale_leaves_nothing_behind(store, ranking, changes, message):
    before = state(store)

    with pytest.raises(BusinessRuleError, match=message):
        register(store, ranking, **({"items": [("P1", 1)]} | changes))

    assert state(store) == before
    assert ranking.counted == {}


@pytest.mark.unit
def test_every_problem_is_reported_at_once(store, ranking):
    with pytest.raises(BusinessRuleError) as rejected:
        register(store, ranking, [("P4", 1)], id_cliente="C3", id_farmaceutico="F3")

    assert rejected.value.errors == [
        "El cliente C3 está dado de baja",
        "El farmacéutico F3 está inactivo",
        "El producto P4 está discontinuado",
    ]


@pytest.mark.unit
def test_if_the_stock_fails_neither_the_sale_nor_the_prescription_change(store, ranking):
    before = state(store)

    # P1 is covered, P2 is not: there are 5 units.
    with pytest.raises(BusinessRuleError, match="insuficiente de P2: se pidieron 6 y hay 5"):
        register(store, ranking, [("P1", 2), ("P2", 6)], id_receta="R1")

    assert state(store) == before  # no sale, same prescription, same batches, same counters
    assert ranking.counted == {}


@pytest.mark.unit
def test_the_ranking_counts_the_units_after_the_sale_is_stored(store, ranking):
    register(store, ranking, [("P1", 2), ("P2", 1), ("P1", 1)], id_receta="R1")

    assert ranking.counted == {"V001": {"P1": 3, "P2": 1}}


@pytest.mark.unit
def test_a_failure_of_the_ranking_does_not_fail_the_sale(store):
    result = register(store, RecordingRanking(broken=True), [("P1", 1)])

    assert result["venta"]["id_venta"] == "V001"
    assert "V001" in store.sales


@pytest.mark.unit
def test_a_missing_ranking_is_not_started_with_a_single_sale(store):
    ranking = RecordingRanking(exists=False)

    register(store, ranking, [("P1", 1)])

    assert ranking.counted == {}  # q07 rebuilds it whole from MongoDB


@pytest.mark.unit
def test_the_same_request_sent_twice_registers_one_sale(store, ranking):
    keys = InMemoryIdempotencyKeys()
    register(store, ranking, [("P1", 1)], idempotency=keys, idempotency_key="k-1")

    with pytest.raises(BusinessRuleError, match="k-1 ya fue recibida y registró la venta V001"):
        register(store, ranking, [("P1", 1)], idempotency=keys, idempotency_key="k-1")

    assert list(store.sales) == ["V001"]
    assert store.units()["L1"] == 49


@pytest.mark.unit
def test_a_rejected_request_can_be_sent_again_with_the_same_key(store, ranking):
    keys = InMemoryIdempotencyKeys()
    with pytest.raises(BusinessRuleError):
        register(store, ranking, [("P1", 99)], idempotency=keys, idempotency_key="k-1")

    result = register(store, ranking, [("P1", 1)], idempotency=keys, idempotency_key="k-1")

    assert result["venta"]["id_venta"] == "V001"


# --- Against MongoDB and Redis ----------------------------------------------------------


def register_in_mongo(database, items, id_receta=None, **changes) -> dict:
    arguments = {
        "id_cliente": "C101",
        "id_farmaceutico": "F101",  # works at S101
        "items": items,
        "medio_pago": "Débito",
        "id_receta": id_receta,
    }
    return register_sale(
        MongoUnitOfWork(database), ProductRanking(get_redis()), CLOCK, **(arguments | changes)
    )


def snapshot(database) -> dict:
    """Everything a sale can write in MongoDB."""
    return {
        name: list(database[name].find().sort("_id"))
        for name in ("ventas", "recetas", "lotes", COUNTERS)
    }


def consistent(database) -> bool:
    return product_ranking_differences(database, ProductRanking(get_redis())) == []


@pytest.mark.integration
def test_sale_prescription_and_stock_are_stored_together(loaded_for_writing):
    database = loaded_for_writing
    units_before = ProductRanking(get_redis()).all()

    # RC102 is a simple, valid prescription of C101. PRD103 is sold under prescription.
    result = register_in_mongo(database, [("PRD101", 2), ("PRD103", 1)], id_receta="RC102")

    assert result["venta"]["id_venta"] == "V118"  # the loaded sales end at V117
    stored = database.ventas.find_one({"_id": "V118"})
    assert (stored["estado"], stored["tipo"], stored["id_sucursal"], stored["stock_aplicado"]) == (
        "Completada",
        "Con receta",
        "S101",
        True,
    )
    assert stored["items"] == [
        {"id_detalle": "D120", "id_producto": "PRD101", "cantidad": 2, "precio_unit": 3900},
        {"id_detalle": "D121", "id_producto": "PRD103", "cantidad": 1, "precio_unit": 8400},
    ]
    assert stored["total"] == 2 * 3900 + 8400

    recipe = database.recetas.find_one({"_id": "RC102"})
    assert (recipe["dispensas_realizadas"], recipe["estado"]) == (1, "Completada")

    # FEFO at S101: PRD101 from L101 (L117 is logically deleted), PRD103 from L102.
    assert database.lotes.find_one({"_id": "L101"})["unidades"] == 118
    assert database.lotes.find_one({"_id": "L102"})["unidades"] == 29

    # Redis follows MongoDB: the ranking counted the sale, once.
    units_after = ProductRanking(get_redis()).all()
    assert units_after["PRD101"] == units_before["PRD101"] + 2
    assert consistent(database)


@pytest.mark.integration
def test_if_the_stock_fails_nothing_is_stored(loaded_for_writing):
    database = loaded_for_writing
    before = snapshot(database)

    # PRD103 has 110 non-expired units at S101.
    with pytest.raises(BusinessRuleError, match="de PRD103: se pidieron 111 y hay 110"):
        register_in_mongo(database, [("PRD101", 2), ("PRD103", 111)], id_receta="RC102")

    # No sale, the prescription untouched, no batch touched and no identifier used.
    assert snapshot(database) == before
    assert consistent(database)


@pytest.mark.integration
def test_two_simultaneous_sales_cannot_use_the_same_single_dispense(loaded_for_writing):
    database = loaded_for_writing

    def sell(_: int) -> bool:
        try:
            register_in_mongo(database, [("PRD103", 1)], id_receta="RC102")
        except BusinessRuleError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(sell, range(4)))

    assert outcomes.count(True) == 1
    assert database.recetas.find_one({"_id": "RC102"})["dispensas_realizadas"] == 1
    assert database.ventas.count_documents({"id_receta": "RC102"}) == 1
    assert database.lotes.find_one({"_id": "L102"})["unidades"] == 29
    assert consistent(database)


@pytest.mark.integration
def test_idempotency_key_in_redis_stops_a_repeated_request(loaded_for_writing):
    database = loaded_for_writing
    keys = RedisIdempotencyKeys(get_redis())
    request = {"idempotency": keys, "idempotency_key": "caja1-0001"}
    register_in_mongo(database, [("PRD101", 1)], **request)

    with pytest.raises(BusinessRuleError, match="ya fue recibida y registró la venta V118"):
        register_in_mongo(database, [("PRD101", 1)], **request)

    assert database.ventas.count_documents({"_id": {"$gte": "V118"}}) == 1
    assert get_redis().ttl(f"{get_settings().redis_prefix}idem:q14:caja1-0001") > 0  # it expires


@pytest.mark.integration
def test_command_line_registers_a_sale(loaded_for_writing, capsys, monkeypatch):
    monkeypatch.setenv("FARMARED_TODAY", TODAY.isoformat())
    get_settings.cache_clear()
    sale = ["q14", "--cliente", "C101", "--farmaceutico", "F101", "--medio-pago", "Débito"]

    assert main([*sale, "--item", "PRD101:2", "--item", "PRD103:1", "--receta", "RC102"]) == 0
    assert '"id_venta": "V118"' in capsys.readouterr().out

    assert main([*sale, "--item", "PRD103:1"]) == 1
    assert "son de venta bajo receta y no se indicó receta" in capsys.readouterr().out

    assert consistent(loaded_for_writing)
