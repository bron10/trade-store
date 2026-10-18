# API contract

Base URL for local Compose: `http://127.0.0.1:8000`.

Dates are `YYYY-MM-DD`. Timestamps are ISO-8601 with a UTC offset. Field names are snake_case.

## `POST /trades`

Insert or replace the current trade.

Request:

```json
{
  "trade_id": "TRD-1",
  "version": 1,
  "counterparty_id": "CP-1",
  "portfolio_id": "PF-1",
  "maturity_date": "2026-12-31",
  "created_date": "2026-01-15"
}
```

| Status | When |
| --- | --- |
| `201` | The trade ID was inserted |
| `200` | The existing row was replaced |
| `409` | The incoming version is lower than the stored version |
| `422` | The body is invalid, or the maturity date is before the business date |
| `500` | An unexpected failure occurred |

Response:

```json
{
  "trade_id": "TRD-1",
  "version": 1,
  "counterparty_id": "CP-1",
  "portfolio_id": "PF-1",
  "maturity_date": "2026-12-31",
  "created_date": "2026-01-15",
  "store_created_at": "2026-10-16T15:00:00Z",
  "store_updated_at": "2026-10-16T15:00:00Z",
  "expired": false
}
```

## `POST /trades/bulk`

Request:

```json
{
  "trades": [
    {
      "trade_id": "TRD-1",
      "version": 1,
      "counterparty_id": "CP-1",
      "portfolio_id": "PF-1",
      "maturity_date": "2026-12-31",
      "created_date": "2026-01-15"
    }
  ]
}
```

The envelope must be a JSON object with a `trades` array of 1 to `BULK_MAX_ITEMS` elements. Elements are validated one by one. A non-object element becomes a rejected item and does not stop the batch.

Response item:

```json
{
  "index": 0,
  "trade_id": "TRD-1",
  "outcome": "created",
  "status_code": 201,
  "trade": {},
  "error": null
}
```

`outcome` is `created`, `replaced`, or `rejected`. `trade` is present for success. `error` is present for rejection and uses `code`, `message`, and `details`.

Item status codes: `201`, `200`, `409`, `422`, and `500`.

Overall status:

| Status | When |
| --- | --- |
| `200` | Every item was created or replaced |
| `207` | At least one item was rejected. Successful items stay committed |
| `422` | The envelope itself is invalid, including an empty list or a batch over the maximum |

`207` is used for partial success because the HTTP response has more than one status. Callers must read `results` whenever the status is `200` or `207`.

Duplicate IDs in `trades` are applied in input order, each in its own transaction. See [requirements.md](requirements.md).

## `GET /trades/{trade_id}`

Returns the current trade, or `404` with code `trade_not_found`. An ID that fails the identifier pattern is `422`.

## `GET /trades`

Query parameters:

| Name | Default | Rule |
| --- | --- | --- |
| `limit` | `50` | Integer from 1 through 100 |
| `offset` | `0` | Integer from 0 through 1,000,000 |

Invalid values are `422`. Ordering is `store_updated_at DESC, trade_id ASC`, which stays stable when timestamps tie.

```json
{
  "items": [],
  "limit": 50,
  "offset": 0,
  "total": 0
}
```

An offset past the end returns an empty `items` array and the real `total`.

## `GET /health`

Liveness. It does not check PostgreSQL.

```json
{"status": "ok"}
```

## `GET /ready`

Readiness. It checks that the API can open a database connection and run `SELECT 1`.

```json
{"status": "ready"}
```

When the check fails the status is `503` and the body is `{"status": "unavailable"}`.

## Error envelope

Used by the trade endpoints and by request validation:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": {
      "errors": [
        {"loc": ["body", "version"], "msg": "Input should be greater than 0", "type": "greater_than"}
      ]
    }
  }
}
```

| Code | HTTP |
| --- | --- |
| `validation_error` | `422` |
| `maturity_in_past` | `422` |
| `invalid_batch` | `422` |
| `version_conflict` | `409` |
| `trade_not_found` | `404` |
| `not_found` | `404` |
| `method_not_allowed` | `405` |
| `internal_error` | `500` |

`version_conflict` details include `trade_id`, `incoming_version`, and `stored_version`. `maturity_in_past` details include `trade_id`, `maturity_date`, `business_date`, and `business_timezone`.
