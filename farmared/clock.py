"""Source of the current date.

Every query that depends on "today" (last 60 days, current month, last year, expired batches)
asks a Clock, so no date is ever fixed in the code and tests can run on a known day.
"""

from datetime import date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from farmared.config import get_settings


class Clock(Protocol):
    def today(self) -> date: ...


class SystemClock:
    """System date in the configured time zone (Argentina by default)."""

    def __init__(self, timezone: str) -> None:
        self._tz = ZoneInfo(timezone)

    def today(self) -> date:
        return datetime.now(self._tz).date()


class FixedClock:
    """Always returns the same day. For tests and reproducible demos."""

    def __init__(self, day: date) -> None:
        self._day = day

    def today(self) -> date:
        return self._day


def get_clock() -> Clock:
    settings = get_settings()
    if settings.farmared_today is not None:
        return FixedClock(settings.farmared_today)
    return SystemClock(settings.timezone)
