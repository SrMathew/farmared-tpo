"""Multi-document transactions.

All the writes of a business operation go in one transaction: either all of them are
stored or none is. It is what keeps q14 and q15 together (sale, prescription, batches and
identifier counters).
"""

from collections.abc import Callable

from pymongo.client_session import ClientSession
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from farmared.adapters.mongo.connection import get_client


def run_in_transaction[T](work: Callable[[ClientSession], T]) -> T:
    """Run `work(session)` in a transaction and return its result.

    - Every read sees the same snapshot of the data and writes are majority-committed.
    - If `work` raises (a business rule is not met, stock is not enough), the transaction
      is aborted, nothing is stored and the exception reaches the caller.
    - If MongoDB reports a transient conflict (two sales competing for the same batch), the
      whole `work` is run again; so `work` must only write through `session`.
    - Each call opens its own session: sessions are not shared between threads.
    """
    with get_client().start_session() as session:
        return session.with_transaction(
            work,
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern("majority"),
        )
