from datetime import UTC, datetime

from app.clock import FixedClock


def test_business_date_uses_the_configured_timezone() -> None:
    instant = datetime(2026, 10, 16, 14, 30, tzinfo=UTC)
    clock = FixedClock(instant, "Pacific/Auckland")
    assert clock.now() == instant
    assert clock.business_today().isoformat() == "2026-10-17"


def test_business_date_can_be_the_previous_local_day() -> None:
    instant = datetime(2026, 10, 16, 2, 0, tzinfo=UTC)
    clock = FixedClock(instant, "America/Los_Angeles")
    assert clock.business_today().isoformat() == "2026-10-15"
    assert clock.now().utcoffset() is not None
    assert clock.now().utcoffset().total_seconds() == 0
