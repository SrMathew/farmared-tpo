"""q07 - Top 5 best-selling products by units, counting only completed sales."""

import pytest

from farmared.adapters.mongo import queries
from farmared.adapters.redis.connection import get_redis
from farmared.adapters.redis.product_ranking import ProductRanking
from farmared.cli import main
from farmared.loading.writer import clear_derived_data
from farmared.services.q07_top_products import top_products
from farmared.services.redis_sync import product_ranking_differences, rebuild_product_ranking

pytestmark = pytest.mark.integration


@pytest.fixture
def ranking(loaded):
    """The ranking in Redis, rebuilt from the loaded data before every test."""
    ranking = ProductRanking(get_redis())
    rebuild_product_ranking(loaded, ranking)
    return ranking


def test_top_five_products_by_units_sold(loaded, ranking):
    # PRD101: five units from V102 and V109; the one of V117 (logically deleted) does not count.
    assert top_products(loaded, ranking) == [
        {"id_producto": "PRD005", "nombre": "Metformina 850mg x60", "unidades": 6},
        {"id_producto": "PRD011", "nombre": "Loratadina 10mg x10", "unidades": 5},
        {"id_producto": "PRD101", "nombre": "Ibuprofeno 600 mg x 10", "unidades": 5},
        {"id_producto": "PRD106", "nombre": "Vitamina C 1 g x 10", "unidades": 5},
        {"id_producto": "PRD108", "nombre": "Pantoprazol 40 mg x 28", "unidades": 5},
    ]


def test_ranking_in_redis_matches_the_sales_in_mongodb(loaded, ranking):
    assert product_ranking_differences(loaded, ranking) == []

    from_mongodb = list(queries.units_sold_by_product(loaded).items())[:5]
    from_redis = [(row["id_producto"], row["unidades"]) for row in top_products(loaded, ranking)]
    assert from_redis == from_mongodb


def test_only_completed_sales_count(loaded, ranking):
    units = ranking.all()

    # PRD007: one unit in V001 (completed); the unit of V011 (pending) does not count.
    assert units["PRD007"] == 1
    # PRD002 only appears in V012 (pending) and V015 (cancelled).
    assert "PRD002" not in units
    assert not {"V011", "V012", "V015"} & ranking.counted_sales()


def test_limit_is_a_parameter(loaded, ranking):
    assert [row["id_producto"] for row in top_products(loaded, ranking, limit=3)] == [
        "PRD005",
        "PRD011",
        "PRD101",
    ]


def test_ranking_is_rebuilt_from_mongodb_when_redis_lost_it(loaded, ranking):
    clear_derived_data(get_redis())
    assert ranking.exists() is False

    assert top_products(loaded, ranking)[0] == {
        "id_producto": "PRD005",
        "nombre": "Metformina 850mg x60",
        "unidades": 6,
    }
    assert product_ranking_differences(loaded, ranking) == []


def test_a_difference_with_mongodb_is_detected_and_repaired(loaded, ranking):
    ranking.add_sale("V999", {"PRD001": 10})  # a sale MongoDB does not have

    assert product_ranking_differences(loaded, ranking) == [
        "ranking: PRD001 tiene 14 unidades en Redis y 4 en MongoDB",
        "ranking: la venta V999 fue contada y no está completada",
    ]

    rebuild_product_ranking(loaded, ranking)
    assert product_ranking_differences(loaded, ranking) == []


def test_command_line_prints_the_result(loaded, ranking, capsys):
    assert main(["q07", "--limit", "2"]) == 0

    output = capsys.readouterr().out
    assert "q07 - Top 2 productos más vendidos" in output
    assert "Metformina 850mg x60" in output
