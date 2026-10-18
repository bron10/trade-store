# Trade Store

Prototype REST API that stores the current version of a financial trade. A later version replaces the stored row. A lower version is rejected. Historical versions are not retained.

The API, PostgreSQL, and a separate expiry worker run with Docker Compose. This repository is prepared for technical review. It does not authenticate callers and it does not deploy to a cloud provider.

## Architecture

- The FastAPI process validates input and applies versioned inserts and replacements.
- PostgreSQL stores one current row per `trade_id`.
- A one-shot migration container applies Alembic migrations before the API or worker starts.
- The expiry worker is a separate process. It marks trades expired after their maturity date and does not run inside API workers.

See [docs/architecture.md](docs/architecture.md) and the diagrams in [docs/diagrams](docs/diagrams).

## Technology stack

Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL 16, Psycopg 3, Alembic, pytest, HTTPX, Ruff, uv, Docker Compose, and GitHub Actions. Security scanning uses pip-audit and Trivy.

Python 3.12 is the project interpreter because it is a current stable release with first-class support in this stack. The system Python on a workstation may be older. uv installs 3.12 for local commands, and the image is based on `python:3.12-slim-bookworm`.

## Prerequisites

- Docker with Compose v2
- uv, for local tests and non-container development
- Optional: Trivy, for the same scans the CI workflow runs

## Local development

```bash
uv python install 3.12
uv sync
cp .env.example .env
```

Start only the database, then migrate and run the processes on the host:

```bash
docker compose up -d db
export DATABASE_URL=postgresql+psycopg://trade:trade@127.0.0.1:5432/trade_store
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
uv run python -m app.workers.expiry
```

If `.env` changes `POSTGRES_PASSWORD`, use that password in `DATABASE_URL`. The API does not read the Compose database password on its own.

## Docker Compose

From a clean checkout, without a `.env` file:

```bash
docker compose up --build
```

The API listens on `http://127.0.0.1:8000`. PostgreSQL is published on `127.0.0.1:5432` so host-side tests can reach it. That port is for local development.

Compose starts three application concerns:

1. `db` — PostgreSQL, with the named volume `trade_store_data`
2. `migrate` — runs `alembic upgrade head` and exits
3. `api` and `worker` — start only after the database is healthy and `migrate` has exited successfully

Startup order is not treated as readiness. The database has a health check, and the worker waits until the `trades` table exists.

Stop the stack:

```bash
docker compose down
```

`docker compose down -v` also deletes the database volume.

Run migrations again after a schema change:

```bash
docker compose run --rm migrate
```

## API examples

Create a trade:

```bash
curl -s -X POST http://127.0.0.1:8000/trades \
  -H 'content-type: application/json' \
  -d '{"trade_id":"TRD-1","version":1,"counterparty_id":"CP-1","portfolio_id":"PF-1","maturity_date":"2026-12-31","created_date":"2026-01-15"}'
```

Replace it with a higher version:

```bash
curl -s -X POST http://127.0.0.1:8000/trades \
  -H 'content-type: application/json' \
  -d '{"trade_id":"TRD-1","version":2,"counterparty_id":"CP-1","portfolio_id":"PF-9","maturity_date":"2026-12-31","created_date":"2026-01-15"}'
```

Bulk ingestion, fetch, and list:

```bash
curl -s -X POST http://127.0.0.1:8000/trades/bulk \
  -H 'content-type: application/json' \
  -d '{"trades":[{"trade_id":"TRD-2","version":1,"counterparty_id":"CP-1","portfolio_id":"PF-1","maturity_date":"2026-12-31","created_date":"2026-01-15"}]}'

curl -s http://127.0.0.1:8000/trades/TRD-1
curl -s 'http://127.0.0.1:8000/trades?limit=20&offset=0'
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/ready
```

Interactive OpenAPI is served at `/docs`. The contract is written out in [docs/api-contract.md](docs/api-contract.md).

## Tests

The integration tests create and truncate `trade_store_test`. Point `DATABASE_URL` at that database, never at a database whose contents you need to keep.

```bash
docker compose up -d db
export DATABASE_URL=postgresql+psycopg://trade:trade@127.0.0.1:5432/trade_store_test
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`pytest` applies Alembic migrations to the test database. Unit tests do not need PostgreSQL. API, integration, and regression tests do.

## Security scans

```bash
uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file /tmp/requirements.txt
uv run pip-audit --requirement /tmp/requirements.txt
docker build --tag trade-store:local .
trivy fs --scanners vuln,secret,misconfig --severity CRITICAL --exit-code 1 .
trivy image --scanners vuln,secret,misconfig --severity CRITICAL --exit-code 1 trade-store:local
```

### Vulnerability policy

- A Trivy finding at `CRITICAL` severity fails the build. Critical is the blocker class for that scanner.
- pip-audit has no severity scale. Every vulnerability it reports fails the build and is treated as a blocker.
- High, medium, and low Trivy findings are visible in the scan output and still need review. They do not fail this prototype's gate.
- There is no blanket ignore file. A legitimate exception needs a reviewed, dated, and narrow suppression that names the CVE, the affected package, and why the risk is accepted. Prefer upgrading or replacing the dependency.
- Pull requests from forks do not receive secrets. This workflow does not use repository secrets.

GitHub branch protection is not configured by the workflow. Protect `main` manually, require the CI workflow, and require review before merging.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Compose default points at service `db` | SQLAlchemy URL using the `postgresql+psycopg` driver |
| `POSTGRES_USER` | `trade` | Database role created by the Postgres image |
| `POSTGRES_PASSWORD` | `trade` | Local placeholder password |
| `POSTGRES_DB` | `trade_store` | Application database |
| `BUSINESS_TIMEZONE` | `UTC` | IANA timezone used for the business calendar date |
| `EXPIRY_INTERVAL_SECONDS` | `60` | Delay between expiry runs |
| `BULK_MAX_ITEMS` | `100` | Maximum trades accepted in one bulk request |
| `LOG_LEVEL` | `INFO` | Python log level |
| `EXPIRY_HEARTBEAT_PATH` | `/tmp/expiry-heartbeat` | File touched after a successful expiry run |

Copy [`.env.example`](.env.example) to `.env` before any shared deployment and replace the password. Do not commit `.env`. The image does not contain secrets. Credentials are supplied at runtime.

`DATABASE_URL` must use the same user, password, and database name as the Postgres settings. Inside Compose the host name is `db`.

## Known limitations

- Callers are not authenticated or authorized.
- Only the current trade row is stored.
- Equal versions both succeed; the later committed write wins the non-version fields.
- Duplicate trade IDs in one bulk request are applied one after another. See the requirements document.
- Expiry becomes visible on the next worker run, not at the instant the business date changes.
- Offset pagination gets slower as the table grows.
- The published Postgres port is a local-development convenience.
- OpenAPI is exposed on the API port.
