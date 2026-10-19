from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from tests.support import new_trade

from app.clock import FixedClock
from app.errors import VersionConflictError
from app.services.trades import TradeService


def test_concurrent_writers_keep_the_highest_version(database, clock: FixedClock) -> None:
    service = TradeService(clock, database, 100)
    service.ingest(new_trade(version=1))
    versions = [1, 3, 2, 5, 4, 1, 6, 2, 7, 3]
    barrier = Barrier(len(versions))

    def attempt(version: int) -> str:
        barrier.wait(timeout=10)
        try:
            service.ingest(new_trade(version=version))
        except VersionConflictError:
            return "conflict"
        return "ok"

    with ThreadPoolExecutor(max_workers=len(versions)) as pool:
        outcomes = list(pool.map(attempt, versions))

    assert service.get_trade("TRD-1").version == max(versions)
    assert "ok" in outcomes
    assert "conflict" in outcomes
