"""Query results are printed as JSON with ISO dates."""

import json
from datetime import date, datetime

import pytest

from farmared.output import to_json

pytestmark = pytest.mark.unit


def test_dates_are_written_in_iso_format():
    result = {
        "fecha": datetime(2026, 10, 13),
        "vencimiento": date(2027, 8, 31),
        "creada_en": datetime(2026, 10, 13, 15, 30, 5),
    }

    assert json.loads(to_json(result)) == {
        "fecha": "2026-10-13",
        "vencimiento": "2027-08-31",
        "creada_en": "2026-10-13T15:30:05",
    }


def test_accented_text_is_kept_readable():
    assert "Fernández" in to_json({"apellido": "Fernández"})
