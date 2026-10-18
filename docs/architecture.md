# Architecture

## Components

| Component | Responsibility |
| --- | --- |
| `app/api` | HTTP routes, status codes, and response models |
| `app/schemas` | Pydantic request and response validation |
| `app/services` | Maturity checks, bulk item isolation, and transaction boundaries |
| `app/repositories` | Locking, versioned writes, queries, and expiry updates |
| `app/models` | SQLAlchemy mapping for `trades` |
| `app/db` | Engine, session factory, and PostgreSQL error inspection |
| `app/workers` | Expiry loop for a separate process |
| `migrations` | Alembic schema, constraints, and the version trigger |
| PostgreSQL | Current trade rows and transactional locks |

`main.py` builds the app, dependency wiring, and error handlers. Business rules are not placed there.

## Data flow

1. FastAPI validates the JSON shape for a single trade, or accepts the bulk envelope and validates each element separately.
2. The service compares `maturity_date` with `clock.business_today()`.
3. The repository opens a transaction, takes `pg_advisory_xact_lock(hashtextextended(trade_id, 0))`, and reads the current row `FOR UPDATE`.
4. `decide_version` selects insert, replace, or conflict.
5. A conflict rolls the transaction back and the API returns `409`. An insert or replace commits and returns `201` or `200`.
6. The expiry worker runs the same clock rule in its own process and updates only rows that are newly expired.

Bulk ingestion repeats that flow once per item. A failure commits nothing for that item and the loop continues.

## Concurrency control

The advisory lock covers the first insert as well as later updates. A row lock alone cannot serialize two transactions that both see "no row".

Under the lock:

- a missing row is inserted
- `incoming >= stored` replaces the economic fields, refreshes `store_updated_at`, sets `expired` to false, and leaves `created_date` and `store_created_at` unchanged
- `incoming < stored` returns the stored row without writing

The trigger `trades_version_monotonic` rejects an update whose new version is lower, including SQL that bypasses the repository. The positive-version check constraint rejects `version < 1`.

PostgreSQL's default `READ COMMITTED` isolation is sufficient because the lock makes the read and write atomic for one trade ID. `hashtextextended` is 64-bit. A hash collision would serialize two unrelated IDs; it would not let an older version win.

Expiry is one `UPDATE ... WHERE expired = false AND maturity_date < business_date RETURNING trade_id`. If a replacement commits a new future maturity first, the worker's predicate no longer matches that row. If the worker marks the row expired first, a later valid replacement clears the flag. Repeating the worker updates zero rows.

## Deployment shape

Compose runs `db`, `migrate`, `api`, and `worker` on the `trade_store` network. The API and worker share one image and use different commands. Migrations run in `migrate` and are not executed by every API process, so multiple API replicas would not each try to migrate. This prototype starts one API container and one worker.

The database volume is `trade_store_data`. Credentials come from the environment. The image runs as uid 10001.

`/health` is liveness and does not touch the database. `/ready` runs `SELECT 1`. Compose uses `/ready` for the API health check. The worker writes a heartbeat file only after a successful expiry pass.

## Error handling

Domain errors become the shared error envelope. Unhandled exceptions are logged with database userinfo redacted and returned as `internal_error` without a stack trace. Bulk items catch database failures locally so one bad write does not abort the rest of the batch.
