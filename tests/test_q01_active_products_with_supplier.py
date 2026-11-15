"""q01 - Active products with all the data of their supplier."""

import pytest

from farmared.adapters.mongo import queries
from farmared.adapters.redis.catalog_cache import CatalogCache
from farmared.adapters.redis.connection import key
from farmared.cli import main
from farmared.services.q01_active_products_with_supplier import active_products_with_supplier

pytestmark = pytest.mark.integration


@pytest.fixture
def cache(redis_client):
    return CatalogCache(redis_client, ttl_seconds=300)


def test_lists_only_active_products(loaded, cache):
    products = active_products_with_supplier(loaded, cache)["productos"]
    ids = [product["id_producto"] for product in products]

    assert len(products) == 20  # 11 active of the course + 9 active of the team
    assert ids == sorted(ids)
    assert "PRD012" not in ids and "PRD013" not in ids and "PRD110" not in ids  # inactive
    assert all(product["activo"] for product in products)


def test_each_product_carries_every_field_of_its_supplier(loaded, cache):
    products = active_products_with_supplier(loaded, cache)["productos"]

    assert products[0] == {
        "id_producto": "PRD001",
        "nombre": "Paracetamol 500mg x30",
        "principio_activo": "Paracetamol",
        "categoria": "Analgésico",
        "presentacion": "Comprimidos x30",
        "condicion_venta": "Venta libre",
        "precio_unit": 2800,
        "activo": True,
        "proveedor": {
            "id_proveedor": "PRV001",
            "razon_social": "Laboratorios Andinos S.A.",
            "cuit": "30-71234567-1",
            "tipo": "Laboratorio",
            "ciudad": "Buenos Aires",
            "provincia": "Buenos Aires",
            "telefono": "1143001100",
            "activo": True,
        },
    }


def test_first_read_comes_from_mongodb_and_the_next_from_redis(loaded, cache):
    first = active_products_with_supplier(loaded, cache)
    second = active_products_with_supplier(loaded, cache)

    assert (first["origen"], second["origen"]) == ("mongodb", "redis")
    assert second["productos"] == first["productos"]


def test_cached_copy_is_the_same_as_the_data_in_mongodb(loaded, cache):
    active_products_with_supplier(loaded, cache)

    assert cache.get() == queries.active_products_with_supplier(loaded)


def test_cache_can_be_skipped_and_is_refreshed(loaded, cache):
    active_products_with_supplier(loaded, cache)

    assert active_products_with_supplier(loaded, cache, use_cache=False)["origen"] == "mongodb"


def test_cached_copy_expires(loaded, cache, redis_client):
    active_products_with_supplier(loaded, cache)

    assert 0 < redis_client.ttl(key("cache", "q01")) <= 300


def test_command_line_prints_the_result(loaded, capsys):
    assert main(["q01"]) == 0

    output = capsys.readouterr().out
    assert "q01 - Productos activos con su proveedor" in output
    assert "Laboratorios Andinos S.A." in output
