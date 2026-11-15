"""Command line: run each query of the assignment.

    python -m farmared q01 [--no-cache]
    python -m farmared q02
    python -m farmared q03 C006
    python -m farmared q04

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
from farmared.services.q03_customer_history import customer_history
from farmared.services.q04_customers_with_several_prescriptions import (
    customers_with_several_prescriptions,
)


def _q01(args: argparse.Namespace) -> None:
    cache = CatalogCache(get_redis(), get_settings().cache_ttl_seconds)
    result = active_products_with_supplier(get_database(), cache, use_cache=not args.no_cache)
    print_result("q01 - Productos activos con su proveedor", result)


def _q02(args: argparse.Namespace) -> None:
    print_result("q02 - Ventas pendientes con su farmacéutico", pending_sales(get_database()))


def _q03(args: argparse.Namespace) -> None:
    result = customer_history(get_database(), args.id_cliente)
    print_result(f"q03 - Historial del cliente {args.id_cliente}", result)


def _q04(args: argparse.Namespace) -> None:
    result = customers_with_several_prescriptions(get_database())
    print_result("q04 - Clientes con más de una receta", result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="farmared", description="Consultas del TPO FarmaRed")
    commands = parser.add_subparsers(dest="query", required=True, metavar="consulta")

    q01 = commands.add_parser("q01", help="Productos activos con los datos de su proveedor")
    q01.add_argument("--no-cache", action="store_true", help="leer siempre de MongoDB")
    q01.set_defaults(run=_q01)

    q02 = commands.add_parser("q02", help="Ventas pendientes con farmacéutico, sucursal y total")
    q02.set_defaults(run=_q02)

    q03 = commands.add_parser("q03", help="Historial de un cliente: ventas y recetas por fecha")
    q03.add_argument("id_cliente", help="identificador del cliente, por ejemplo C006")
    q03.set_defaults(run=_q03)

    q04 = commands.add_parser("q04", help="Clientes con más de una receta y cuántas tienen")
    q04.set_defaults(run=_q04)

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
