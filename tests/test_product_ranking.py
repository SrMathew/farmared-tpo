"""The product ranking kept in Redis (q07): idempotent, ordered and rebuildable."""

import fakeredis
import pytest

from farmared.adapters.redis.product_ranking import ProductRanking

pytestmark = pytest.mark.unit


@pytest.fixture
def ranking():
    return ProductRanking(fakeredis.FakeRedis(decode_responses=True))


def test_an_empty_ranking_has_no_products(ranking):
    assert ranking.exists() is False
    assert ranking.top(5) == []
    assert ranking.all() == {}


def test_adding_a_sale_counts_the_units_of_each_product(ranking):
    assert ranking.add_sale("V001", {"PRD001": 2, "PRD002": 1}) is True
    assert ranking.add_sale("V002", {"PRD001": 3}) is True

    assert ranking.all() == {"PRD001": 5, "PRD002": 1}
    assert ranking.counted_sales() == {"V001", "V002"}
    assert ranking.exists() is True


def test_adding_the_same_sale_twice_counts_it_once(ranking):
    ranking.add_sale("V001", {"PRD001": 2})

    assert ranking.add_sale("V001", {"PRD001": 2}) is False
    assert ranking.all() == {"PRD001": 2}


def test_top_returns_the_best_sellers_highest_first(ranking):
    ranking.rebuild({"PRD001": 4, "PRD002": 9, "PRD003": 1}, ["V001"])

    assert ranking.top(2) == [("PRD002", 9), ("PRD001", 4)]


def test_products_with_the_same_units_are_ordered_by_identifier(ranking):
    ranking.rebuild({"PRD108": 5, "PRD011": 5, "PRD005": 6, "PRD106": 5, "PRD101": 5}, [])

    # Three places for four products tied at 5: the lowest identifiers take them.
    assert ranking.top(4) == [("PRD005", 6), ("PRD011", 5), ("PRD101", 5), ("PRD106", 5)]


def test_top_with_fewer_products_than_asked_returns_them_all(ranking):
    ranking.rebuild({"PRD001": 4}, [])

    assert ranking.top(5) == [("PRD001", 4)]


def test_rebuild_replaces_whatever_was_there(ranking):
    ranking.add_sale("V001", {"PRD001": 2})
    ranking.add_sale("V999", {"PRD999": 50})  # something MongoDB does not have

    ranking.rebuild({"PRD001": 2, "PRD002": 7}, ["V001", "V002"])

    assert ranking.all() == {"PRD001": 2, "PRD002": 7}
    assert ranking.counted_sales() == {"V001", "V002"}


def test_rebuild_with_no_sales_leaves_the_ranking_empty(ranking):
    ranking.add_sale("V001", {"PRD001": 2})

    ranking.rebuild({}, [])

    assert ranking.all() == {}
    assert ranking.counted_sales() == set()
