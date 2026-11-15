"""Generation of new business identifiers (V017, C009...).

MongoDB has no auto-increment field, so the last number of each sequence is kept in a
document of the `counters` collection. `$inc` is atomic on the server: two concurrent
requests never get the same number. When it runs inside a transaction that is later
aborted, the counter goes back too, so the numbering has no gaps.
"""

from enum import StrEnum
from typing import Any

from pymongo import ReturnDocument
from pymongo.client_session import ClientSession
from pymongo.database import Database

from farmared.adapters.mongo.documents import COUNTERS

_DIGITS = 3


class Sequence(StrEnum):
    """Each sequence is named after its entity; the value is the prefix of its identifiers."""

    CUSTOMER = "C"
    BRANCH = "S"
    PHARMACIST = "F"
    SUPPLIER = "PRV"
    PRODUCT = "PRD"
    BATCH = "L"
    PRESCRIPTION = "RC"
    SALE = "V"
    SALE_ITEM = "D"


def format_id(sequence: Sequence, number: int) -> str:
    return f"{sequence.value}{number:0{_DIGITS}d}"


def number_of(sequence: Sequence, identifier: str) -> int:
    """Numeric part of an identifier: number_of(Sequence.SALE, 'V016') -> 16."""
    return int(identifier.removeprefix(sequence.value))


def next_ids(
    database: Database[dict[str, Any]],
    sequence: Sequence,
    count: int = 1,
    session: ClientSession | None = None,
) -> list[str]:
    """Reserve `count` consecutive identifiers of a sequence and return them in order."""
    counter = database[COUNTERS].find_one_and_update(
        {"_id": sequence.name},
        {"$inc": {"seq": count}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
        session=session,
    )
    assert counter is not None  # upsert + ReturnDocument.AFTER always return the document
    last = counter["seq"]
    return [format_id(sequence, number) for number in range(last - count + 1, last + 1)]


def set_last_number(database: Database[dict[str, Any]], sequence: Sequence, last: int) -> None:
    """Start a sequence after `last`. Used by the data load, with the highest loaded number."""
    database[COUNTERS].replace_one({"_id": sequence.name}, {"seq": last}, upsert=True)
