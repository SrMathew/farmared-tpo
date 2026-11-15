"""The MongoDB data model: collections, validators, indexes and identifier counters."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from pymongo.errors import WriteError

from farmared.adapters.mongo.documents import to_document
from farmared.adapters.mongo.ids import Sequence, next_ids
from farmared.adapters.mongo.schema import VALIDATORS
from farmared.domain.models import Batch

pytestmark = pytest.mark.integration


def batch_document(**changes) -> dict:
    batch = Batch(
        id_lote="L900",
        id_producto="PRD001",
        id_sucursal="S001",
        nro_lote="N-1",
        unidades=10,
        vencimiento=date(2027, 1, 31),
    )
    return {**to_document(batch), **changes}


# --- Collections and validators ---------------------------------------------------------


def test_every_business_collection_exists_with_its_validator(database):
    names = set(database.list_collection_names())

    assert set(VALIDATORS) | {"counters"} <= names
    assert len(VALIDATORS) == 8


def test_every_business_collection_requires_the_logical_delete_flag():
    for name, validator in VALIDATORS.items():
        assert "activo" in validator["$jsonSchema"]["required"], name


@pytest.mark.parametrize(
    "changes",
    [
        {"unidades": -1},  # stock can never be negative
        {"vencimiento": "2027-01-31"},  # a date stored as text
    ],
)
def test_validator_rejects_invalid_documents(database, changes):
    with pytest.raises(WriteError):
        database.lotes.insert_one(batch_document(**changes))


def test_validator_also_guards_updates(database):
    database.lotes.insert_one(batch_document(unidades=3))

    with pytest.raises(WriteError):
        database.lotes.update_one({"_id": "L900"}, {"$inc": {"unidades": -5}})


def test_fefo_index_exists(database):
    keys = [index["key"] for index in database.lotes.list_indexes()]

    assert {"id_sucursal": 1, "id_producto": 1, "vencimiento": 1} in [dict(k) for k in keys]


# --- Identifier counters ----------------------------------------------------------------


def test_identifiers_are_consecutive(database):
    assert next_ids(database, Sequence.SALE) == ["V001"]
    assert next_ids(database, Sequence.SALE) == ["V002"]
    assert next_ids(database, Sequence.SALE_ITEM, count=3) == ["D001", "D002", "D003"]


def test_concurrent_requests_never_get_the_same_identifier(database):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: next_ids(database, Sequence.CUSTOMER)[0], range(40)))

    assert len(set(results)) == 40
    assert sorted(results)[-1] == "C040"
