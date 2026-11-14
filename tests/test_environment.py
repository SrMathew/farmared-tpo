"""The dev container services are reachable and configured as the project needs."""

import os

import pytest
import redis
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017/?replicaSet=rs0")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")


@pytest.mark.integration
def test_mongodb_is_a_replica_set():
    # Multi-document transactions (q14 + q15) only work on a replica set.
    client: MongoClient = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    assert client.admin.command("ping")["ok"] == 1.0
    assert client.admin.command("hello").get("setName") == "rs0"


@pytest.mark.integration
def test_redis_responds():
    assert redis.Redis.from_url(REDIS_URL, socket_connect_timeout=5).ping() is True
