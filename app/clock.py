from datetime import UTC, date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo


class Clock(Protocol):
    timezone_name: str

    def now(self) -> datetime:
        """Return the current instant as a timezone-aware UTC timestamp."""

    def business_today(self) -> date:
        """Return the calendar date in the configured business timezone."""


class SystemClock:
    def __init__(self, business_timezone: str) -> None:
        self.timezone_name = business_timezone
        self._zone = ZoneInfo(business_timezone)

    def now(self) -> datetime:
        return datetime.now(UTC)

    def business_today(self) -> date:
        return datetime.now(self._zone).date()


class FixedClock:
    """Deterministic clock for tests and support reproductions."""

    def __init__(self, instant: datetime, business_timezone: str) -> None:
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("instant must be timezone-aware")
        self.timezone_name = business_timezone
        self._instant = instant.astimezone(UTC)
        self._zone = ZoneInfo(business_timezone)

    def now(self) -> datetime:
        return self._instant

    def business_today(self) -> date:
        return self._instant.astimezone(self._zone).date()
