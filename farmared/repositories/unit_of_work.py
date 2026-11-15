"""A unit of work: several reads and writes that are stored all together or not at all."""

from collections.abc import Callable
from typing import Protocol


class UnitOfWork[Store](Protocol):
    def run[T](self, work: Callable[[Store], T]) -> T:
        """Run `work(store)` and return its result.

        Everything `work` writes through `store` is stored only if it finishes. If it raises,
        nothing is stored and the exception reaches the caller. `work` can be run more than
        once (when two operations compete for the same data), so it must only read and
        write through `store`.
        """
        ...
