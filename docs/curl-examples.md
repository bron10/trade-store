# Curl examples

Base URL: `http://127.0.0.1:8000`

Start the stack first with `docker compose up --build`. Dates must be on or after today's business date. The examples below use dates that stay valid through 2026.

## POST /trades

Insert a trade. The first request for an ID returns `201`.

```bash
curl -sS -X POST http://127.0.0.1:8000/trades \
  -H 'content-type: application/json' \
  -d '{"trade_id":"TRD-1","version":1,"counterparty_id":"CP-1","portfolio_id":"PF-1","maturity_date":"2026-12-31","created_date":"2026-01-15"}'
```

Replace it with an equal or higher version. This returns `200` and keeps the original `created_date`.

```bash
curl -sS -X POST http://127.0.0.1:8000/trades \
  -H 'content-type: application/json' \
  -d '{"trade_id":"TRD-1","version":2,"counterparty_id":"CP-2","portfolio_id":"PF-9","maturity_date":"2026-12-31","created_date":"2026-01-15"}'
```

Send a lower version. This returns `409` and leaves the stored trade unchanged.

```bash
curl -sS -X POST http://127.0.0.1:8000/trades \
  -H 'content-type: application/json' \
  -d '{"trade_id":"TRD-1","version":1,"counterparty_id":"CP-1","portfolio_id":"PF-1","maturity_date":"2026-12-31","created_date":"2026-01-15"}'
```

## POST /trades/bulk

Ingest several trades in one request. The response has one result per input item, in the same order. A fully successful batch returns `200`. A batch with any rejected item returns `207`.

```bash
curl -sS -X POST http://127.0.0.1:8000/trades/bulk \
  -H 'content-type: application/json' \
  -d '{"trades":[{"trade_id":"TRD-2","version":1,"counterparty_id":"CP-1","portfolio_id":"PF-1","maturity_date":"2026-12-31","created_date":"2026-01-15"},{"trade_id":"TRD-3","version":1,"counterparty_id":"CP-1","portfolio_id":"PF-1","maturity_date":"2020-01-01","created_date":"2026-01-15"}]}'
```

## GET /trades/{trade_id}

Return the current trade. A missing ID returns `404`.

```bash
curl -sS http://127.0.0.1:8000/trades/TRD-1
```

## GET /trades

Return a page of trades. `limit` defaults to 50 and `offset` defaults to 0. Ordering is `store_updated_at` descending, then `trade_id` ascending.

```bash
curl -sS 'http://127.0.0.1:8000/trades?limit=20&offset=0'
```

## GET /health

Liveness check. This does not contact the database.

```bash
curl -sS http://127.0.0.1:8000/health
```

## GET /ready

Readiness check. This returns `200` when the API can reach PostgreSQL, and `503` when it cannot.

```bash
curl -sS http://127.0.0.1:8000/ready
```
