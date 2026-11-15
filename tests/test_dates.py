"""Clock and date helpers."""

from datetime import date, datetime

import pytest

from farmared.clock import FixedClock, SystemClock, get_clock
from farmared.dates import month_start, next_month_start, parse_date, to_datetime

pytestmark = pytest.mark.unit

TODAY = date(2026, 10, 13)


def test_clock_uses_the_system_date_by_default(monkeypatch):
    monkeypatch.delenv("FARMARED_TODAY", raising=False)

    clock = get_clock()

    assert isinstance(clock, SystemClock)
    assert isinstance(clock.today(), date)


def test_clock_can_be_fixed_for_tests_and_demos(monkeypatch):
    monkeypatch.setenv("FARMARED_TODAY", "2026-10-13")

    clock = get_clock()

    assert isinstance(clock, FixedClock)
    assert clock.today() == TODAY


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-09-10", date(2026, 9, 10)),
        ("", None),
        (None, None),
        ("HOY", TODAY),
        ("HOY-30", date(2026, 9, 13)),
        ("HOY+90", date(2027, 1, 11)),
    ],
)
def test_parse_date(value, expected):
    assert parse_date(value, TODAY) == expected


def test_parse_date_rejects_other_formats():
    with pytest.raises(ValueError):
        parse_date("13/10/2026", TODAY)


def test_a_day_is_stored_as_its_midnight():
    assert to_datetime(TODAY) == datetime(2026, 10, 13, 0, 0)


def test_month_boundaries():
    assert month_start(TODAY) == date(2026, 10, 1)
    assert next_month_start(TODAY) == date(2026, 11, 1)
    assert next_month_start(date(2026, 12, 31)) == date(2027, 1, 1)
