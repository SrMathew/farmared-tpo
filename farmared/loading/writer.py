"""Write a validated dataset into MongoDB and reset what Redis derives from it."""

from typing import Any

from pymongo.database import Database
from redis import Redis

from farmared.adapters.mongo.documents import COLLECTIONS, to_document
from farmared.adapters.mongo.ids import Sequence, number_of, set_last_number
from farmared.adapters.mongo.schema import reset_schema
from farmared.adapters.redis.connection import key
from farmared.domain.models import (
    Batch,
    Branch,
    Customer,
    Entity,
    Pharmacist,
    Prescription,
    Product,
    Sale,
    Supplier,
)
from farmared.loading.reader import Dataset

_SEQUENCES: dict[type[Entity], Sequence] = {
    Customer: Sequence.CUSTOMER,
    Branch: Sequence.BRANCH,
    Pharmacist: Sequence.PHARMACIST,
    Supplier: Sequence.SUPPLIER,
    Product: Sequence.PRODUCT,
    Batch: Sequence.BATCH,
    Prescription: Sequence.PRESCRIPTION,
    Sale: Sequence.SALE,
}


def write_dataset(database: Database[dict[str, Any]], dataset: Dataset) -> dict[str, int]:
    """Empty the collections and store the dataset. Returns the documents per collection.

    Starting from empty collections is what makes the load idempotent: running it again
    leaves exactly the same state.
    """
    reset_schema(database)
    counts = {}
    for model, (collection, _) in COLLECTIONS.items():
        entities = dataset.of(model)
        if entities:
            database[collection].insert_many([to_document(e) for e in entities.values()])
        counts[collection] = len(entities)
        # New identifiers continue after the highest one loaded.
        sequence = _SEQUENCES[model]
        set_last_number(
            database, sequence, max((number_of(sequence, i) for i in entities), default=0)
        )

    item_ids = [item.id_detalle for sale in dataset.sales.values() for item in sale.items]
    set_last_number(
        database,
        Sequence.SALE_ITEM,
        max((number_of(Sequence.SALE_ITEM, i) for i in item_ids), default=0),
    )
    return counts


def clear_derived_data(redis: Redis) -> int:
    """Delete every key of the system in Redis. Returns how many were deleted.

    Redis only holds data derived from MongoDB. After a reload that data would describe the
    previous contents, so it is removed rather than left contradicting MongoDB.
    """
    keys = list(redis.scan_iter(match=key("*")))
    if keys:
        redis.delete(*keys)
    return len(keys)
