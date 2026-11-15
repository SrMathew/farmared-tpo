"""The data load, end to end: read, validate, and only then write."""

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from pymongo.database import Database
from redis import Redis

from farmared.domain.errors import BusinessRuleError
from farmared.loading.reader import Dataset, read_dataset
from farmared.loading.validation import validate
from farmared.loading.writer import clear_derived_data, write_dataset

logger = logging.getLogger(__name__)


@dataclass
class LoadReport:
    counts: dict[str, int]  # documents stored per collection
    observations: list[str]  # loaded as they are, but worth knowing (see validation.py)


def read_and_validate(directories: list[Path], today: date) -> tuple[Dataset, list[str]]:
    """Read the CSV files and check every rule. Returns the dataset and its observations.

    Raises BusinessRuleError with every problem found if any rule is broken.
    """
    dataset, errors = read_dataset(directories, today)
    observations: list[str] = []
    if not errors:
        errors, observations = validate(dataset, today)
    if errors:
        raise BusinessRuleError(errors)
    return dataset, observations


def load_data(
    database: Database[dict[str, Any]], redis: Redis, data_dir: Path, today: date
) -> LoadReport:
    """Migrate `data_dir/given` (course) and `data_dir/added` (team) into MongoDB.

    Nothing is written unless the whole dataset is valid, so a failed load leaves the
    databases exactly as they were.
    """
    dataset, observations = read_and_validate([data_dir / "given", data_dir / "added"], today)
    counts = write_dataset(database, dataset)
    deleted = clear_derived_data(redis)
    logger.info("Loaded %s; %d derived Redis keys cleared", counts, deleted)
    return LoadReport(counts, observations)
