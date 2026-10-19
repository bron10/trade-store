from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from tests.support import payload

from app.repositories.trades import TradeRepository


def _error(response, status: int, code: str) -> dict:
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    return body


def test_create_get_and_replace(client: TestClient) -> None:
    created = client.post("/trades", json=payload())
    assert created.status_code == 201
    body = created.json()
    assert body["trade_id"] == "TRD-1"
    assert body["expired"] is False
    assert body["created_date"] == "2026-01-15"
    stored_at = datetime.fromisoformat(body["store_created_at"])
    updated_at = datetime.fromisoformat(body["store_updated_at"])
    assert stored_at.utcoffset() is not None
    assert updated_at.utcoffset() is not None
    assert body["store_created_at"] == body["store_updated_at"]

    fetched = client.get("/trades/TRD-1")
    assert fetched.status_code == 200
    assert fetched.json() == body

    replaced = client.post(
        "/trades",
        json=payload(version=2, counterparty_id="CP-2", created_date="2020-01-01"),
    )
    assert replaced.status_code == 200
    assert replaced.json()["version"] == 2
    assert replaced.json()["counterparty_id"] == "CP-2"
    assert replaced.json()["created_date"] == "2026-01-15"
    assert replaced.json()["store_created_at"] == body["store_created_at"]

    conflict = client.post("/trades", json=payload(version=1))
    error = _error(conflict, 409, "version_conflict")
    assert error["error"]["details"]["stored_version"] == 2
    assert error["error"]["details"]["incoming_version"] == 1


def test_equal_version_replaces(client: TestClient) -> None:
    assert client.post("/trades", json=payload()).status_code == 201
    replaced = client.post("/trades", json=payload(portfolio_id="PF-2"))
    assert replaced.status_code == 200
    assert replaced.json()["portfolio_id"] == "PF-2"
    assert replaced.json()["version"] == 1


def test_missing_trade_and_invalid_identifier(client: TestClient) -> None:
    _error(client.get("/trades/MISSING"), 404, "trade_not_found")
    _error(client.get("/trades/_bad"), 422, "validation_error")


def test_validation_and_maturity_errors(client: TestClient) -> None:
    missing = client.post("/trades", json={"trade_id": "TRD-1"})
    _error(missing, 422, "validation_error")
    expired = client.post("/trades", json=payload(expired=True))
    _error(expired, 422, "validation_error")
    past = client.post("/trades", json=payload(maturity_date="2026-10-15"))
    error = _error(past, 422, "maturity_in_past")
    assert error["error"]["details"]["business_timezone"] == "UTC"
    today = client.post("/trades", json=payload(trade_id="TODAY", maturity_date="2026-10-16"))
    assert today.status_code == 201
    assert today.json()["expired"] is False


def test_pagination_is_stable_and_validated(client: TestClient) -> None:
    for trade_id in ("B", "A", "C"):
        assert client.post("/trades", json=payload(trade_id=trade_id)).status_code == 201
    page = client.get("/trades", params={"limit": 2, "offset": 0})
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert [item["trade_id"] for item in body["items"]] == ["A", "B"]
    rest = client.get("/trades", params={"limit": 2, "offset": 2})
    assert [item["trade_id"] for item in rest.json()["items"]] == ["C"]
    empty = client.get("/trades", params={"limit": 50, "offset": 10})
    assert empty.json()["items"] == []
    assert empty.json()["total"] == 3
    _error(client.get("/trades", params={"limit": 0}), 422, "validation_error")
    _error(client.get("/trades", params={"limit": 101}), 422, "validation_error")
    _error(client.get("/trades", params={"offset": -1}), 422, "validation_error")
    _error(client.get("/trades", params={"limit": "many"}), 422, "validation_error")


def test_bulk_partial_success_and_duplicates(client: TestClient) -> None:
    response = client.post(
        "/trades/bulk",
        json={
            "trades": [
                payload(trade_id="KEEP", version=1, created_date="2024-02-02"),
                payload(trade_id="BAD", maturity_date="2020-01-01"),
                payload(trade_id="KEEP", version=1, portfolio_id="PF-9", created_date="1999-01-01"),
                payload(trade_id="KEEP", version=4, portfolio_id="PF-4"),
                payload(trade_id="KEEP", version=2),
            ]
        },
    )
    assert response.status_code == 207
    results = response.json()["results"]
    assert [item["index"] for item in results] == [0, 1, 2, 3, 4]
    assert results[0]["status_code"] == 201
    assert results[1]["status_code"] == 422
    assert results[1]["error"]["code"] == "maturity_in_past"
    assert results[2]["status_code"] == 200
    assert results[3]["status_code"] == 200
    assert results[4]["status_code"] == 409
    stored = client.get("/trades/KEEP").json()
    assert stored["version"] == 4
    assert stored["created_date"] == "2024-02-02"
    assert stored["portfolio_id"] == "PF-4"
    assert client.get("/trades/BAD").status_code == 404


def test_bulk_all_success_is_200(client: TestClient) -> None:
    response = client.post(
        "/trades/bulk",
        json={"trades": [payload(trade_id="ONE"), payload(trade_id="TWO")]},
    )
    assert response.status_code == 200
    assert [item["outcome"] for item in response.json()["results"]] == ["created", "created"]


def test_bulk_envelope_errors(client: TestClient) -> None:
    _error(client.post("/trades/bulk", json={"trades": []}), 422, "validation_error")
    _error(
        client.post("/trades/bulk", json={"extra": True, "trades": [payload()]}),
        422,
        "validation_error",
    )
    oversized = [payload(trade_id=f"T{index}") for index in range(101)]
    error = _error(client.post("/trades/bulk", json={"trades": oversized}), 422, "invalid_batch")
    assert error["error"]["details"]["max_items"] == 100


def test_database_failures_do_not_leak_internals(client: TestClient, monkeypatch) -> None:
    def explode(self, trade, *, now, expired):
        raise OperationalError(
            "INSERT",
            {},
            Exception("postgresql://trade:secret-pass@db:5432/trade_store"),
        )

    monkeypatch.setattr(TradeRepository, "apply", explode)
    single = client.post("/trades", json=payload())
    _error(single, 500, "internal_error")
    assert "secret-pass" not in single.text
    assert "postgresql" not in single.text.lower()
    assert "Traceback" not in single.text

    bulk = client.post("/trades/bulk", json={"trades": [payload(), payload(trade_id="OTHER")]})
    assert bulk.status_code == 207
    assert "secret-pass" not in bulk.text
    assert all(item["error"]["code"] == "internal_error" for item in bulk.json()["results"])


def test_health_and_openapi(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]
    assert "/trades" in paths
    assert "/trades/bulk" in paths
    assert "/trades/{trade_id}" in paths
    assert "/health" in paths
    assert "/ready" in paths


def test_readiness_hides_database_errors(client: TestClient, app) -> None:
    class BrokenEngine:
        def connect(self):
            raise OSError("db down")

    original = app.state.engine
    app.state.engine = BrokenEngine()
    try:
        assert client.get("/health").status_code == 200
        ready = client.get("/ready")
        assert ready.status_code == 503
        assert ready.json() == {"status": "unavailable"}
        assert "db down" not in ready.text
    finally:
        app.state.engine = original
