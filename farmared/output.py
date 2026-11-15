"""Readable output of query results: JSON with ISO dates."""

import json
from datetime import date, datetime, time
from typing import Any


def _convert(value: Any) -> str:
    if isinstance(value, datetime):
        # Dates are stored as midnight datetimes: show them as plain dates.
        if value.time() == time.min:
            return value.date().isoformat()
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def to_json(result: Any) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2, default=_convert)


def print_result(title: str, result: Any) -> None:
    print(f"\n=== {title} ===")
    print(to_json(result))
