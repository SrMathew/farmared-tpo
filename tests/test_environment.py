"""The dev container services are reachable and configured as the project needs."""

import pytest

from farmared.adapters.mongo.connection import get_client, get_database
from farmared.adapters.redis.connection import get_redis

pytestmark = pytest.mark.integration


def test_mongodb_is_a_replica_set():
    # Multi-document transactions (q14 + q15) only work on a replica set.
    assert get_client().admin.command("ping")["ok"] == 1.0
    assert get_client().admin.command("hello").get("setName") == "rs0"


def test_mongodb_database_uses_majority_concerns():
    database = get_database()

    assert database.name == "farmared_test"  # the test session uses its own database
    assert database.write_concern.document == {"w": "majority"}
    assert database.read_concern.level == "majority"


def test_mongodb_supports_multi_document_transactions():
    collection = get_database()["_transaction_check"]
    collection.drop()
    with get_client().start_session() as session, session.start_transaction():
        collection.insert_one({"_id": 1}, session=session)
        session.abort_transaction()

    assert collection.count_documents({}) == 0
    collection.drop()


def test_redis_responds():
    assert get_redis().ping() is True
