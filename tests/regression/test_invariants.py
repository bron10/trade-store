from datetime import date

from fastapi.testclient import TestClient
from tests.support import payload


def test_replacement_preserves_created_date_and_rejects_client_expiry(client: TestClient) -> None:
    created = client.post("/trades", json=payload(created_date="2024-05-01"))
    assert created.status_code == 201
    replaced = client.post(
        "/trades",
        json=payload(version=1, created_date="2010-01-01", portfolio_id="PF-8"),
    )
    assert replaced.status_code == 200
    assert replaced.json()["created_date"] == "2024-05-01"
    assert replaced.json()["portfolio_id"] == "PF-8"
    rejected = client.post("/trades", json=payload(version=2, expired=False))
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "validation_error"
    assert client.get("/trades/TRD-1").json()["version"] == 1


def test_bulk_duplicate_order_is_sequential(client: TestClient) -> None:
    response = client.post(
        "/trades/bulk",
        json={
            "trades": [
                payload(trade_id="DUP", version=2, created_date="2023-03-03"),
                payload(trade_id="DUP", version=2, maturity_date="2026-11-01"),
                payload(trade_id="DUP", version=1),
            ]
        },
    )
    assert response.status_code == 207
    codes = [item["status_code"] for item in response.json()["results"]]
    assert codes == [201, 200, 409]
    stored = client.get("/trades/DUP").json()
    assert stored["version"] == 2
    assert stored["maturity_date"] == "2026-11-01"
    assert stored["created_date"] == "2023-03-03"


def test_trade_maturing_today_is_not_expired(client: TestClient) -> None:
    response = client.post(
        "/trades",
        json=payload(trade_id="TODAY", maturity_date=date(2026, 10, 16).isoformat()),
    )
    assert response.status_code == 201
    assert response.json()["expired"] is False
