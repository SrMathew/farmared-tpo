"""The data load is a validated migration: every rule is checked before anything is written."""

import csv
import shutil
from datetime import date, datetime
from pathlib import Path

import pytest

from farmared.adapters.mongo.ids import Sequence, next_ids
from farmared.adapters.redis.connection import key
from farmared.domain.errors import BusinessRuleError
from farmared.loading.loader import load_data, read_and_validate

DATA = Path(__file__).resolve().parents[1] / "data"
TODAY = date(2026, 11, 15)

KNOWN_OBSERVATIONS = [
    "V001 (Completada): El farmacéutico F004 está inactivo",
    "V014 (Completada): El producto PRD012 está discontinuado",
    "RC002: la próxima dispensa es 2026-09-15 y la última dispensa (2026-08-15) + 30 días "
    "da 2026-09-14",
]

FILES = [
    "clientes",
    "sucursales",
    "farmaceuticos",
    "proveedores",
    "productos",
    "stock_lotes",
    "recetas",
    "ventas",
    "detalle_ventas",
]


def data_with(tmp_path: Path, file: str, old: str, new: str) -> Path:
    """A copy of the datasets where one piece of text of a course CSV was changed."""
    copy = tmp_path / "data"
    shutil.copytree(DATA, copy)
    path = copy / "given" / f"{file}.csv"
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} is not in {file}.csv"
    path.write_text(text.replace(old, new), encoding="utf-8")
    return copy


# --- Validation (no database needed) ----------------------------------------------------


@pytest.mark.unit
def test_course_data_alone_is_valid_with_three_known_observations():
    dataset, observations = read_and_validate([DATA / "given"], TODAY)

    assert observations == KNOWN_OBSERVATIONS
    assert len(dataset.sales) == 16


@pytest.mark.unit
@pytest.mark.parametrize("today", [date(2026, 10, 13), TODAY, date(2027, 6, 1)])
def test_additional_records_add_no_observation_whatever_the_day(today):
    # Their dates are relative to today, so they stay valid on any day the load runs.
    dataset, observations = read_and_validate([DATA / "given", DATA / "added"], today)

    assert observations == KNOWN_OBSERVATIONS
    assert len(dataset.sales) == 33


@pytest.mark.unit
@pytest.mark.parametrize("file", FILES)
def test_there_are_at_least_ten_additional_records_per_dataset(file):
    with open(DATA / "added" / f"{file}.csv", encoding="utf-8", newline="") as rows:
        assert len(list(csv.DictReader(rows))) >= 10


@pytest.mark.unit
def test_additional_records_exercise_the_logical_delete_of_every_entity():
    dataset, _ = read_and_validate([DATA / "given", DATA / "added"], TODAY)

    for entities in (
        dataset.customers,
        dataset.branches,
        dataset.pharmacists,
        dataset.suppliers,
        dataset.products,
        dataset.batches,
        dataset.prescriptions,
        dataset.sales,
    ):
        assert any(not entity.activo for entity in entities.values())


@pytest.mark.unit
@pytest.mark.parametrize(
    ("file", "old", "new", "expected"),
    [
        # Prices: the total is the sum of the items.
        ("ventas", "Débito,5750,Completada", "Débito,5000,Completada", "V002: El total"),
        # Referential integrity.
        ("stock_lotes", "L001,PRD001,S001", "L001,PRD999,S001", "L001: el producto PRD999"),
        # Sale condition: prescription of the same customer.
        ("ventas", "V003,C001,F001,RC001", "V003,C001,F001,RC002", "pertenece a otro cliente"),
        # Sale condition: a product under prescription needs one.
        (
            "ventas",
            "V003,C001,F001,RC001,2026-09-10,Con receta",
            "V003,C001,F001,,2026-09-10,Venta libre",
            "V003: Los productos ['PRD003'] son de venta bajo receta",
        ),
        # Sales and branches: only pharmacies sell.
        ("ventas", "V013,C001,F001", "V013,C001,F007", "solo las farmacias registran ventas"),
        # An open (pending) sale cannot reference something inactive.
        (
            "farmaceuticos",
            "Director Técnico,S004,True",
            "Director Técnico,S004,False",
            "V011: El farmacéutico F006 está inactivo",
        ),
        # A pending sale needs a prescription that can still be dispensed.
        ("recetas", "1,0,,Vigente", "1,0,,Vencida", "V011: La receta RC006 está 'Vencida'"),
        # Long-term treatment: dispenses match the completed sales.
        (
            "ventas",
            "Crédito,7100,Completada",
            "Crédito,7100,Anulada",
            "RC008: declara 1 dispensas realizadas y tiene 0 ventas completadas",
        ),
        ("clientes", "C002,Martín,Gómez,28765432", "C002,Martín,Gómez,31245678", "DNI 31245678"),
        ("farmaceuticos", "MN-18078", "MN-18041", "Matrícula MN-18041 repetida"),
        ("ventas", "RC006,2026-10-12", "RC006,2099-01-01", "V011: tiene fecha futura"),
        (
            "stock_lotes",
            "L001,PRD001,S001,L-2501A,120,2027-08-31",
            "L001,PRD001,S001,L-2501A,120,31/08/2027",
            "L001: vencimiento",
        ),
        ("stock_lotes", "L-2501A,120,", "L-2501A,-5,", "L001: unidades"),
        ("clientes", "C002,Martín", "C001,Martín", "C001: identificador duplicado"),
        ("productos", "Bajo receta archivada", "Receta magistral", "PRD008: condicion_venta"),
    ],
)
def test_a_broken_rule_aborts_the_load(tmp_path, file, old, new, expected):
    data = data_with(tmp_path, file, old, new)

    with pytest.raises(BusinessRuleError) as raised:
        read_and_validate([data / "given", data / "added"], TODAY)

    assert any(expected in error for error in raised.value.errors), raised.value.errors


# --- Writing (MongoDB and Redis) --------------------------------------------------------


def snapshot(database) -> dict:
    return {
        name: sorted(database[name].find(), key=lambda d: str(d["_id"]))
        # Views (q11) store no data, so they are not part of the stored state.
        for name in sorted(database.list_collection_names(filter={"type": "collection"}))
    }


@pytest.mark.integration
def test_load_stores_every_entity(database, redis_client):
    report = load_data(database, redis_client, DATA, TODAY)

    assert report.observations == KNOWN_OBSERVATIONS
    assert report.counts == {
        "clientes": 18,
        "sucursales": 15,
        "farmaceuticos": 17,
        "proveedores": 15,
        "productos": 23,
        "lotes": 35,
        "recetas": 20,
        "ventas": 33,
    }
    assert database.lotes.count_documents({}) == 35


@pytest.mark.integration
def test_loaded_sale_embeds_its_items_and_keeps_the_branch_of_its_pharmacist(
    database, redis_client
):
    load_data(database, redis_client, DATA, TODAY)

    sale = database.ventas.find_one({"_id": "V006"})

    assert sale["id_sucursal"] == "S001"
    assert sale["fecha"] == datetime(2026, 8, 1)
    assert [item["id_detalle"] for item in sale["items"]] == ["D007", "D008"]
    assert sale["stock_aplicado"] is True  # completed: already reflected in the stock CSV
    assert sale["activo"] is True
    assert database.ventas.find_one({"_id": "V011"})["stock_aplicado"] is False  # pending


@pytest.mark.integration
def test_new_identifiers_continue_after_the_loaded_ones(database, redis_client):
    load_data(database, redis_client, DATA, TODAY)

    assert next_ids(database, Sequence.SALE) == ["V118"]
    assert next_ids(database, Sequence.SALE_ITEM, count=2) == ["D120", "D121"]
    assert next_ids(database, Sequence.CUSTOMER) == ["C111"]


@pytest.mark.integration
def test_load_is_idempotent(database, redis_client):
    load_data(database, redis_client, DATA, TODAY)
    first = snapshot(database)

    load_data(database, redis_client, DATA, TODAY)

    assert snapshot(database) == first


@pytest.mark.integration
def test_failed_load_writes_nothing(database, redis_client, tmp_path):
    load_data(database, redis_client, DATA, TODAY)
    before = snapshot(database)
    broken = data_with(tmp_path, "ventas", "Débito,5750,Completada", "Débito,5000,Completada")

    with pytest.raises(BusinessRuleError):
        load_data(database, redis_client, broken, TODAY)

    assert snapshot(database) == before


@pytest.mark.integration
def test_load_clears_the_data_redis_derives_from_mongodb(database, redis_client):
    redis_client.set(key("cache", "q01"), "stale")
    redis_client.set("otra-aplicacion", "intacta")

    load_data(database, redis_client, DATA, TODAY)

    assert redis_client.exists(key("cache", "q01")) == 0
    assert redis_client.get("otra-aplicacion") == "intacta"
    redis_client.delete("otra-aplicacion")


@pytest.mark.integration
def test_load_leaves_the_product_ranking_in_redis_matching_mongodb(database, redis_client):
    from farmared.adapters.redis.product_ranking import ProductRanking
    from farmared.services.redis_sync import product_ranking_differences

    load_data(database, redis_client, DATA, TODAY)

    ranking = ProductRanking(redis_client)
    assert product_ranking_differences(database, ranking) == []
    assert len(ranking.counted_sales()) == 26  # completed and not logically deleted
