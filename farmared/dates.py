"""Date helpers shared by the data load and the queries."""

import re
from datetime import date, datetime, timedelta

# Relative dates of the team's additional records: HOY, HOY-30, HOY+90 ("hoy" = today).
_RELATIVE = re.compile(r"^HOY([+-]\d+)?$")


def to_datetime(day: date) -> datetime:
    """MongoDB has no date-only type: a day is stored as its midnight (naive datetime)."""
    return datetime(day.year, day.month, day.day)


def parse_date(value: str | None, today: date) -> date | None:
    """Parse a CSV date: ISO 'YYYY-MM-DD', empty (null) or relative to today ('HOY-30').

    Relative dates are only used in the team's additional records, so their edge cases
    (batches about to expire, overdue prescriptions, sales of this month) stay valid
    whatever day the data is loaded.
    """
    if value is None or value.strip() == "":
        return None
    text = value.strip()
    match = _RELATIVE.match(text)
    if match:
        return today + timedelta(days=int(match.group(1) or 0))
    return date.fromisoformat(text)


def one_year_before(day: date) -> date:
    """The same day of the previous year (February 28 for a February 29)."""
    try:
        return day.replace(year=day.year - 1)
    except ValueError:
        return day.replace(year=day.year - 1, day=28)


def month_start(day: date) -> date:
    return day.replace(day=1)


def next_month_start(day: date) -> date:
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)
