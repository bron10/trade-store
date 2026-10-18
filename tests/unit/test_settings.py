import pytest
from pydantic import ValidationError

from app.config import get_settings


def test_unknown_timezone_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUSINESS_TIMEZONE", "Not/AZone")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://trade:trade@localhost/db")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()
    get_settings.cache_clear()


def test_bulk_limit_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BULK_MAX_ITEMS", "0")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://trade:trade@localhost/db")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()
    get_settings.cache_clear()
