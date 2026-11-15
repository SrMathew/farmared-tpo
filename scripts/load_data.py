"""Load the datasets into MongoDB: the course CSV files plus the team's additional records.

Usage (inside the dev container):

    python scripts/load_data.py        (or: make load)

The load is reproducible and idempotent: it validates everything first, recreates the
collections and stores the data, so running it again leaves the same state. If a business
rule is broken it prints every problem, writes nothing and exits with code 1.
"""

import sys

from farmared.adapters.mongo.connection import get_database
from farmared.adapters.redis.connection import get_redis
from farmared.clock import get_clock
from farmared.config import get_settings
from farmared.domain.errors import BusinessRuleError
from farmared.loading.loader import load_data
from farmared.log import configure_logging


def main() -> int:
    configure_logging()
    today = get_clock().today()
    try:
        report = load_data(get_database(), get_redis(), get_settings().data_dir, today)
    except BusinessRuleError as error:
        print(f"Carga abortada: {len(error.errors)} error(es). No se escribió nada.")
        for problem in error.errors:
            print(f"  - {problem}")
        return 1

    print(f"Carga completa (fecha del sistema: {today.isoformat()})")
    for collection, count in report.counts.items():
        print(f"  {collection:<14} {count:>3}")
    print(f"Observaciones: {len(report.observations)}")
    for observation in report.observations:
        print(f"  - {observation}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
