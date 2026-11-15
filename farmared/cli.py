"""Command line: run each query of the assignment.

    python -m farmared q01 [--no-cache]
    python -m farmared q02

This is the only place that creates the connections and hands them to the services.
"""

import argparse
import sys

from farmared.adapters.mongo.connection import get_database
from farmared.adapters.redis.catalog_cache import CatalogCache
from farmared.adapters.redis.connection import get_redis
from farmared.config import get_settings
from farmared.domain.errors import BusinessRuleError
from farmared.output import print_result
from farmared.services.q01_active_products_with_supplier import active_products_with_supplier
from farmared.services.q02_pending_sales import pending_sales


def _q01(args: argparse.Namespace) -> None:
    cache = CatalogCache(get_redis(), get_settings().cache_ttl_seconds)
    result = active_products_with_supplier(get_database(), cache, use_cache=not args.no_cache)
    print_result("q01 - Productos activos con su proveedor", result)


def _q02(args: argparse.Namespace) -> None:
    print_result("q02 - Ventas pendientes con su farmacéutico", pending_sales(get_database()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="farmared", description="Consultas del TPO FarmaRed")
    commands = parser.add_subparsers(dest="query", required=True, metavar="consulta")

    q01 = commands.add_parser("q01", help="Productos activos con los datos de su proveedor")
    q01.add_argument("--no-cache", action="store_true", help="leer siempre de MongoDB")
    q01.set_defaults(run=_q01)

    q02 = commands.add_parser("q02", help="Ventas pendientes con farmacéutico, sucursal y total")
    q02.set_defaults(run=_q02)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.run(args)
    except BusinessRuleError as error:
        print("Operación rechazada:")
        for problem in error.errors:
            print(f"  - {problem}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
