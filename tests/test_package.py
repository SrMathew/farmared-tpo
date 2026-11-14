"""Smoke test: the package is installed and importable."""

import pytest

import farmared


@pytest.mark.unit
def test_package_exposes_version():
    assert farmared.__version__
