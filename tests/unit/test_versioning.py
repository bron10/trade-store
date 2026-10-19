from app.domain import ApplyOutcome
from app.versioning import decide_version


def test_missing_trade_is_created() -> None:
    assert decide_version(None, 1) is ApplyOutcome.CREATED


def test_equal_version_replaces() -> None:
    assert decide_version(3, 3) is ApplyOutcome.REPLACED


def test_higher_version_replaces() -> None:
    assert decide_version(3, 4) is ApplyOutcome.REPLACED


def test_lower_version_conflicts() -> None:
    assert decide_version(3, 2) is ApplyOutcome.CONFLICT
