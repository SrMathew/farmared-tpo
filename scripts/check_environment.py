"""Check that the dev container can reach MongoDB (as a replica set) and Redis.

Usage (inside the dev container):

    python scripts/check_environment.py

Exits with code 1 if any engine is unreachable or MongoDB is not a replica set
(multi-document transactions need one).
"""

import sys

from farmared.adapters.mongo.connection import get_client
from farmared.adapters.redis.connection import get_redis


def main() -> int:
    ok = True

    try:
        client = get_client()
        client.admin.command("ping")
        replica_set = client.admin.command("hello").get("setName")
        print(f"MongoDB: OK (replica set: {replica_set})")
        if not replica_set:
            print("MongoDB: ERROR - not a replica set, transactions will not work")
            ok = False
    except Exception as exc:  # report any connection problem and keep checking Redis
        print(f"MongoDB: ERROR - {exc}")
        ok = False

    try:
        get_redis().ping()
        print("Redis:   OK")
    except Exception as exc:
        print(f"Redis:   ERROR - {exc}")
        ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
