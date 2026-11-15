"""HTTP interface of the system: the 15 queries as endpoints, documented with Swagger.

Run it with `make api` and open `/docs`. It is a transport layer and nothing else: each
endpoint reads its parameters, calls the same service function the command line calls
(`farmared/services/qXX_*.py`) and returns its result. No rule lives here.

A rejection of a service (BusinessRuleError) is answered with status 400 and the list of
rules that were not met; nothing was modified in that case.
"""

from typing import Any

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, Field

from farmared.adapters.mongo.connection import get_database
from farmared.adapters.mongo.customers import MongoCustomers
from farmared.adapters.mongo.unit_of_work import MongoUnitOfWork
from farmared.adapters.redis.catalog_cache import CatalogCache
from farmared.adapters.redis.connection import get_redis
from farmared.adapters.redis.idempotency_keys import RedisIdempotencyKeys
from farmared.adapters.redis.product_ranking import ProductRanking
from farmared.clock import get_clock
from farmared.config import get_settings
from farmared.domain.errors import BusinessRuleError
from farmared.output import to_json
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
    create_customer,
    deactivate_customer,
    update_customer,
)
from farmared.services.q14_register_sale import register_sale
from farmared.services.q15_update_stock import update_stock

READ = "Lectura"
AGGREGATION = "Agregación"
SERVICE = "Servicio"

app = FastAPI(
    title="FarmaRed",
    description=(
        "Backoffice de una red de farmacias con persistencia políglota: MongoDB (sistema de "
        "registro) y Redis (datos derivados). Las 15 consultas y servicios del TPO de Base "
        "de Datos II (ITBA). Antes de usarla hay que cargar los datos con `make load`."
    ),
    version="1.0.0",
)


def reply(result: Any) -> Response:
    """The result as JSON, written exactly as the command line prints it (ISO dates)."""
    return Response(content=to_json(result), media_type="application/json")


@app.exception_handler(BusinessRuleError)
def rejected(request: Request, error: BusinessRuleError) -> Response:
    return Response(
        content=to_json({"operacion": "rechazada", "errores": error.errors}),
        status_code=400,
        media_type="application/json",
    )


# --- Request bodies of the write services -----------------------------------------------


class NewCustomer(BaseModel):
    nombre: str
    apellido: str
    dni: str
    obra_social: str = "Sin cobertura"
    nro_afiliado: str | None = None
    email: str | None = None
    telefono: str | None = None
    ciudad: str | None = None
    provincia: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "nombre": "Elena",
                    "apellido": "Vidal",
                    "dni": "38123456",
                    "obra_social": "OSDE",
                    "nro_afiliado": "OS-900100",
                    "email": "elena.vidal@mail.com",
                }
            ]
        }
    }


class CustomerChanges(BaseModel):
    """Only the fields sent are changed."""

    email: str | None = None
    telefono: str | None = None
    ciudad: str | None = None
    provincia: str | None = None
    obra_social: str | None = None
    nro_afiliado: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [{"telefono": "1144556677", "obra_social": "Sin cobertura"}]
        }
    }


class SaleLine(BaseModel):
    id_producto: str
    cantidad: int


class NewSale(BaseModel):
    id_cliente: str
    id_farmaceutico: str
    items: list[SaleLine]
    medio_pago: str
    id_receta: str | None = Field(None, description="Solo si hay productos bajo receta")
    clave: str | None = Field(
        None, description="Clave de idempotencia: repetirla no registra otra venta"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id_cliente": "C101",
                    "id_farmaceutico": "F101",
                    "items": [
                        {"id_producto": "PRD101", "cantidad": 2},
                        {"id_producto": "PRD103", "cantidad": 1},
                    ],
                    "medio_pago": "Débito",
                    "id_receta": "RC102",
                }
            ]
        }
    }


# --- q01 to q12: reads and aggregations -------------------------------------------------


@app.get("/q01", tags=[READ], summary="Productos activos con los datos de su proveedor")
def q01(usar_cache: bool = True) -> Response:
    cache = CatalogCache(get_redis(), get_settings().cache_ttl_seconds)
    return reply(active_products_with_supplier(get_database(), cache, use_cache=usar_cache))


@app.get("/q02", tags=[READ], summary="Ventas pendientes con farmacéutico, sucursal y total")
def q02() -> Response:
    return reply(pending_sales(get_database()))


@app.get(
    "/q03/{id_cliente}", tags=[READ], summary="Historial de un cliente: ventas y recetas por fecha"
)
def q03(id_cliente: str) -> Response:
    return reply(customer_history(get_database(), id_cliente))


@app.get("/q04", tags=[AGGREGATION], summary="Clientes con más de una receta y cuántas tienen")
def q04() -> Response:
    return reply(customers_with_several_prescriptions(get_database()))


@app.get(
    "/q05",
    tags=[AGGREGATION],
    summary="Farmacéuticos activos y sus ventas de los últimos 60 días",
)
def q05() -> Response:
    return reply(pharmacist_sales_last_60_days(get_database(), get_clock()))


@app.get(
    "/q06", tags=[READ], summary="Tratamientos prolongados vigentes con la dispensa atrasada"
)
def q06() -> Response:
    return reply(overdue_long_term_prescriptions(get_database(), get_clock()))


@app.get("/q07", tags=[AGGREGATION], summary="Productos más vendidos en unidades (Redis)")
def q07(limite: int = TOP) -> Response:
    return reply(top_products(get_database(), ProductRanking(get_redis()), limite))


@app.get(
    "/q08", tags=[READ], summary="Lotes con poco stock, con producto, sucursal y proveedor"
)
def q08(menos_de: int = LOW_STOCK) -> Response:
    return reply(low_stock_batches(get_database(), menos_de))


@app.get("/q09", tags=[READ], summary="Ventas libres de total bajo, sin las anuladas")
def q09(menos_de: int = SMALL_TOTAL) -> Response:
    return reply(small_over_the_counter_sales(get_database(), menos_de))


@app.get("/q10/{id_sucursal}", tags=[READ], summary="Clientes atendidos en una sucursal")
def q10(id_sucursal: str) -> Response:
    return reply(customers_served_at_branch(get_database(), id_sucursal))


@app.get(
    "/q11", tags=[AGGREGATION], summary="Ingresos por farmacéutico en el mes actual (vista)"
)
def q11() -> Response:
    return reply(pharmacist_income_current_month(get_database(), get_clock()))


@app.get("/q12", tags=[READ], summary="Clientes activos sin ventas en el último año")
def q12() -> Response:
    return reply(customers_without_sales_last_year(get_database(), get_clock()))


# --- q13 to q15: write services ---------------------------------------------------------


@app.post("/q13/clientes", tags=[SERVICE], summary="Alta de un cliente (DNI único)")
def q13_create(customer: NewCustomer) -> Response:
    return reply(create_customer(MongoCustomers(get_database()), **customer.model_dump()))


@app.patch(
    "/q13/clientes/{id_cliente}",
    tags=[SERVICE],
    summary="Modificación de datos de contacto y cobertura de un cliente",
)
def q13_update(id_cliente: str, changes: CustomerChanges) -> Response:
    sent = changes.model_dump(exclude_unset=True)
    return reply(update_customer(MongoCustomers(get_database()), id_cliente, **sent))


@app.delete(
    "/q13/clientes/{id_cliente}",
    tags=[SERVICE],
    summary="Baja lógica de un cliente (no se borra)",
)
def q13_deactivate(id_cliente: str) -> Response:
    return reply(deactivate_customer(MongoCustomers(get_database()), id_cliente))


@app.post(
    "/q14/ventas",
    tags=[SERVICE],
    summary="Registro de una venta completada, con su receta y su stock",
)
def q14(sale: NewSale) -> Response:
    redis = get_redis()
    result = register_sale(
        MongoUnitOfWork(get_database()),
        ProductRanking(redis),
        get_clock(),
        sale.id_cliente,
        sale.id_farmaceutico,
        [(line.id_producto, line.cantidad) for line in sale.items],
        sale.medio_pago,
        id_receta=sale.id_receta,
        idempotency=RedisIdempotencyKeys(redis),
        idempotency_key=sale.clave,
    )
    return reply(result)


@app.post(
    "/q15/ventas/{id_venta}/stock",
    tags=[SERVICE],
    summary="Descuento del stock de una venta registrada (FEFO)",
)
def q15(id_venta: str) -> Response:
    return reply(update_stock(MongoUnitOfWork(get_database()), get_clock(), id_venta))
