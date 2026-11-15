"""The MongoDB data model: collections, validators, indexes, counters and transactions."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from pymongo.errors import DuplicateKeyError, WriteError

from farmared.adapters.mongo.documents import to_document
from farmared.adapters.mongo.ids import Sequence, next_ids, set_last_number
from farmared.adapters.mongo.schema import VALIDATORS
from farmared.adapters.mongo.transactions import run_in_transaction
from farmared.domain.errors import BusinessRuleError
from farmared.domain.models import Batch, Customer

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


def customer_document(id_cliente: str, dni: str) -> dict:
    return to_document(
        Customer(
            id_cliente=id_cliente,
            nombre="Ana",
            apellido="Gil",
            dni=dni,
            obra_social="Sin cobertura",
        )
    )


# --- Collections and validators ---------------------------------------------------------


def test_every_business_collection_exists_with_its_validator(database):
    names = set(database.list_collection_names())

    assert set(VALIDATORS) | {"counters"} <= names
    assert len(VALIDATORS) == 8


def test_every_business_collection_requires_the_logical_delete_flag():
    for name, validator in VALIDATORS.items():
        assert "activo" in validator["$jsonSchema"]["required"], name


def test_valid_document_is_accepted(database):
    database.lotes.insert_one(batch_document())

    assert database.lotes.count_documents({}) == 1


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


def test_validator_rejects_a_document_without_logical_delete_flag(database):
    document = batch_document()
    del document["activo"]

    with pytest.raises(WriteError):
        database.lotes.insert_one(document)


def test_validator_also_guards_updates(database):
    database.lotes.insert_one(batch_document(unidades=3))

    with pytest.raises(WriteError):
        database.lotes.update_one({"_id": "L900"}, {"$inc": {"unidades": -5}})


def test_customer_dni_is_unique(database):
    database.clientes.insert_one(customer_document("C900", "30111222"))

    with pytest.raises(DuplicateKeyError):
        database.clientes.insert_one(customer_document("C901", "30111222"))


def test_fefo_index_exists(database):
    keys = [index["key"] for index in database.lotes.list_indexes()]

    assert {"id_sucursal": 1, "id_producto": 1, "vencimiento": 1} in [dict(k) for k in keys]


# --- Identifier counters ----------------------------------------------------------------


def test_identifiers_are_consecutive(database):
    assert next_ids(database, Sequence.SALE) == ["V001"]
    assert next_ids(database, Sequence.SALE) == ["V002"]
    assert next_ids(database, Sequence.SALE_ITEM, count=3) == ["D001", "D002", "D003"]


def test_sequence_continues_after_the_loaded_data(database):
    set_last_number(database, Sequence.SALE, 16)

    assert next_ids(database, Sequence.SALE) == ["V017"]


def test_concurrent_requests_never_get_the_same_identifier(database):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: next_ids(database, Sequence.CUSTOMER)[0], range(40)))

    assert len(set(results)) == 40
    assert sorted(results)[-1] == "C040"


# --- Transactions -----------------------------------------------------------------------


def test_transaction_stores_all_its_writes(database):
    def work(session):
        database.lotes.insert_one(batch_document(), session=session)
        return next_ids(database, Sequence.SALE, session=session)[0]

    assert run_in_transaction(work) == "V001"
    assert database.lotes.count_documents({}) == 1


def test_failed_transaction_stores_nothing_and_leaves_no_gap_in_identifiers(database):
    def work(session):
        next_ids(database, Sequence.SALE, session=session)
        database.lotes.insert_one(batch_document(), session=session)
        raise BusinessRuleError("Stock vigente insuficiente")

    with pytest.raises(BusinessRuleError):
        run_in_transaction(work)

    assert database.lotes.count_documents({}) == 0
    assert next_ids(database, Sequence.SALE) == ["V001"]  # the aborted number was not used up
