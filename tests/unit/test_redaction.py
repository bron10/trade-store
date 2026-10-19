from app.errors import redact


def test_redact_removes_database_userinfo() -> None:
    message = "failed postgresql://trade:secret-pass@db:5432/trade_store"
    redacted = redact(message)
    assert "secret-pass" not in redacted
    assert "trade:secret-pass" not in redacted
    assert "://***:***@" in redacted
