"""MongoDB connection, created once and shared."""

from functools import lru_cache
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from farmared.config import get_settings


@lru_cache
def get_client() -> MongoClient[dict[str, Any]]:
    # MongoClient is thread-safe and keeps a connection pool: one instance serves every thread.
    return MongoClient(get_settings().mongo_uri, serverSelectionTimeoutMS=5000)


def get_database() -> Database[dict[str, Any]]:
    """The project database, reading and writing only majority-committed data."""
    return get_client().get_database(
        get_settings().mongo_db,
        write_concern=WriteConcern("majority"),
        read_concern=ReadConcern("majority"),
    )
