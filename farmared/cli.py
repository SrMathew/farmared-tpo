"""Command line: run each query of the assignment.

    python -m farmared q01 [--no-cache]
    python -m farmared q02
    python -m farmared q03 C006
    python -m farmared q04
    python -m farmared q05
    python -m farmared q06
    python -m farmared q07 [--limit 5]
    python -m farmared q08 [--below 50]
    python -m farmared q09 [--below 5000]

This is the only place that creates the connections and hands them to the services.
"""

import argparse
import sys

from farmared.adapters.mongo.connection import get_database
from farmared.adapters.mongo.customers import MongoCustomers
from farmared.adapters.mongo.unit_of_work import MongoUnitOfWork
from farmared.adapters.redis.catalog_cache import CatalogCache
from farmared.adapters.redis.connection import get_redis
from farmared.adapters.redis.product_ranking import ProductRanking
from farmared.clock import get_clock
from farmared.config import get_settings
from farmared.domain.errors import BusinessRuleError
from farmared.output import print_result
from farmared.services.q01_active_products_with_supplier import active_products_with_supplier
from farmared.services.q02_pending_sales import pending_sales
from farmared.services.q03_customer_history import customer_history
from farmared.services.q04_customers_with_several_prescriptions import (
    customers_with_several_prescriptions,
)
from farmared.services.q05_pharmacist_sales_last_60_days import pharmacist_sales_last_60_days
from farmared.services.q06_overdue_long_term_prescriptions import (
    overdue_long_term_prescriptions,
)
from farmared.services.q07_top_products import TOP, top_products
from farmared.services.q08_low_stock_batches import LOW_STOCK, low_stock_batches
from farmared.services.q09_small_over_the_counter_sales import (
    SMALL_TOTAL,
    small_over_the_counter_sales,
)
from farmared.services.q10_customers_served_at_branch import customers_served_at_branch
from farmared.services.q11_pharmacist_income_current_month import (
    pharmacist_income_current_month,
)
from farmared.services.q12_customers_without_sales_last_year import (
    customers_without_sales_last_year,
)
from farmared.services.q13_customer_management import (
    EDITABLE_FIELDS,
    create_customer,
    deactivate_customer,
    update_customer,
)
from farmared.services.q15_update_stock import update_stock


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


def _q05(args: argparse.Namespace) -> None:
    result = pharmacist_sales_last_60_days(get_database(), get_clock())
    print_result("q05 - Ventas por farmacéutico activo en los últimos 60 días", result)


def _q06(args: argparse.Namespace) -> None:
    result = overdue_long_term_prescriptions(get_database(), get_clock())
    print_result("q06 - Tratamientos prolongados con dispensa atrasada", result)


def _q07(args: argparse.Namespace) -> None:
    result = top_products(get_database(), ProductRanking(get_redis()), args.limit)
    print_result(f"q07 - Top {args.limit} productos más vendidos", result)


def _q08(args: argparse.Namespace) -> None:
    result = low_stock_batches(get_database(), args.below)
    print_result(f"q08 - Lotes con menos de {args.below} unidades", result)


def _q09(args: argparse.Namespace) -> None:
    result = small_over_the_counter_sales(get_database(), args.below)
    print_result(f"q09 - Ventas libres con total menor a ${args.below}", result)


def _q10(args: argparse.Namespace) -> None:
    result = customers_served_at_branch(get_database(), args.id_sucursal)
    print_result(f"q10 - Clientes atendidos en la sucursal {args.id_sucursal}", result)


def _q11(args: argparse.Namespace) -> None:
    result = pharmacist_income_current_month(get_database(), get_clock())
    print_result("q11 - Ingresos por farmacéutico en el mes actual", result)


def _q12(args: argparse.Namespace) -> None:
    result = customers_without_sales_last_year(get_database(), get_clock())
    print_result("q12 - Clientes activos sin ventas en el último año", result)


def _given(args: argparse.Namespace, fields: tuple[str, ...]) -> dict[str, str]:
    """The optional arguments the user actually wrote."""
    return {field: getattr(args, field) for field in fields if getattr(args, field) is not None}


def _q13_create(args: argparse.Namespace) -> None:
    result = create_customer(
        MongoCustomers(get_database()),
        args.nombre,
        args.apellido,
        args.dni,
        **_given(args, EDITABLE_FIELDS),
    )
    print_result("q13 - Alta de cliente", result)


def _q13_update(args: argparse.Namespace) -> None:
    result = update_customer(
        MongoCustomers(get_database()), args.id_cliente, **_given(args, EDITABLE_FIELDS)
    )
    print_result(f"q13 - Modificación del cliente {args.id_cliente}", result)


def _q13_deactivate(args: argparse.Namespace) -> None:
    result = deactivate_customer(MongoCustomers(get_database()), args.id_cliente)
    print_result(f"q13 - Baja lógica del cliente {args.id_cliente}", result)


def _q15(args: argparse.Namespace) -> None:
    result = update_stock(MongoUnitOfWork(get_database()), get_clock(), args.id_venta)
    print_result(f"q15 - Descuento de stock de la venta {args.id_venta}", result)


def _add_contact_and_coverage(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--email")
    parser.add_argument("--telefono")
    parser.add_argument("--ciudad")
    parser.add_argument("--provincia")
    parser.add_argument("--obra-social", dest="obra_social", help='por ejemplo "OSDE"')
    parser.add_argument("--nro-afiliado", dest="nro_afiliado")


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

    q05 = commands.add_parser(
        "q05", help="Farmacéuticos activos y sus ventas de los últimos 60 días"
    )
    q05.set_defaults(run=_q05)

    q06 = commands.add_parser("q06", help="Tratamientos prolongados vigentes con dispensa atrasada")
    q06.set_defaults(run=_q06)

    q07 = commands.add_parser("q07", help="Productos más vendidos en unidades")
    q07.add_argument("--limit", type=int, default=TOP, help="cuántos listar (por defecto 5)")
    q07.set_defaults(run=_q07)

    q08 = commands.add_parser(
        "q08", help="Lotes con poco stock, con producto, sucursal y proveedor"
    )
    q08.add_argument(
        "--below", type=int, default=LOW_STOCK, help="límite de unidades (por defecto 50)"
    )
    q08.set_defaults(run=_q08)

    q09 = commands.add_parser("q09", help="Ventas libres de total bajo, sin las anuladas")
    q09.add_argument(
        "--below", type=int, default=SMALL_TOTAL, help="límite del total (por defecto 5000)"
    )
    q09.set_defaults(run=_q09)

    q10 = commands.add_parser("q10", help="Clientes atendidos en una sucursal")
    q10.add_argument("id_sucursal", help="identificador de la sucursal, por ejemplo S002")
    q10.set_defaults(run=_q10)

    q11 = commands.add_parser("q11", help="Ingresos por farmacéutico en el mes actual (vista)")
    q11.set_defaults(run=_q11)

    q12 = commands.add_parser("q12", help="Clientes activos sin ventas en el último año")
    q12.set_defaults(run=_q12)

    q13 = commands.add_parser("q13", help="Clientes: alta, modificación y baja lógica")
    operations = q13.add_subparsers(dest="operation", required=True, metavar="operación")

    create = operations.add_parser("alta", help="Dar de alta un cliente (DNI único)")
    create.add_argument("--nombre", required=True)
    create.add_argument("--apellido", required=True)
    create.add_argument("--dni", required=True)
    _add_contact_and_coverage(create)
    create.set_defaults(run=_q13_create)

    update = operations.add_parser("modificar", help="Cambiar datos de contacto y cobertura")
    update.add_argument("id_cliente", help="identificador del cliente, por ejemplo C101")
    _add_contact_and_coverage(update)
    update.set_defaults(run=_q13_update)

    deactivate = operations.add_parser("baja", help="Dar de baja lógica un cliente")
    deactivate.add_argument("id_cliente", help="identificador del cliente, por ejemplo C101")
    deactivate.set_defaults(run=_q13_deactivate)

    q15 = commands.add_parser("q15", help="Descontar el stock de una venta registrada (FEFO)")
    q15.add_argument("id_venta", help="identificador de la venta, por ejemplo V118")
    q15.set_defaults(run=_q15)

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
