# Architecture and contributor guide

PrintEase is a modular monolith. Browser pages, JSON APIs, payment callbacks and the
printer protocol run in one FastAPI application. PostgreSQL is the durable source
of truth. PDFs live in one persistent filesystem directory. Caddy supplies HTTPS
in the optional production Compose overlay. No Redis, message broker, service mesh
or second database is required.

## Directory map

| Directory/file | Responsibility | Put new code here when… |
| --- | --- | --- |
| `main.py` | Application composition, lifespan, HTML routes, global errors and health checks | Wiring a router, middleware or application resource |
| `config.py` | Typed environment configuration and production validation | Adding a deploy-time setting |
| `core/` | Request correlation, security middleware and JSON logging | Adding infrastructure shared across features |
| `authentication/` | Password hashing, signed cookies and user/admin dependencies | Changing identity verification |
| `routers/` | HTTP parsing, authorization, response contracts and feature endpoints | Adding an API feature |
| `schemas/` | Pydantic request/response contracts, validation and serialization | Defining public inputs or outputs |
| `models/` | SQLAlchemy mapped tables, engine, sessions and DB dependencies | Adding durable data |
| `services/` | Payment workflows, audit recording and printer coordination | Reusing business behavior across endpoints |
| `utils/` | PDF validation, pricing, rate limiting and queue estimates | Adding a small focused helper |
| `migrations/` | Reviewed, versioned database schema changes | Changing a table or index |
| `templates/`, `static/` | Jinja pages and browser assets | Updating the user interface |
| `scripts/` | Database baseline verification and PDF.js asset maintenance | Adding an operator or maintenance command |
| `deploy/`, Compose, Dockerfile | Runtime and HTTPS configuration | Changing deployment behavior |
| `docs/` | Contributor and operator instructions | Explaining decisions or operational procedures |
| `printer-pc/` | Existing Windows printer agent artifacts | Working on the physical printing client |

Keep these explicit boundaries without adding a generic repository abstraction for
every query. A simple endpoint may query SQLAlchemy directly. Move a workflow into
a service when it is shared, complex or needs an independent transaction policy.
The existing import paths are retained to reduce migration risk.

## Request and transaction lifecycle

1. Middleware validates host/origin, assigns a request ID, adds security headers and logs completion.
2. FastAPI validates the request using Pydantic.
3. `CurrentUser` or `CurrentAdmin` verifies token type, expiry, version and database identity.
4. `DBSession` supplies one `AsyncSession` for that request. Never share it between concurrent tasks.
5. Router/service changes state and explicitly commits. Exceptions roll back; closing the session also cleans up unfinished transactions.
6. Response models constrain public output. Password hashes and configuration secrets never belong in response schemas.

The printer reaper creates its own sessions. Password hashing, provider SDK calls
and PDF inspection execute outside the event loop. The PDF parser has size and page
limits, but does not run in an isolated sandbox; see `SECURITY.md` for that boundary.

## Durable versus process-local state

Users, admins, token versions, orders, payments, webhook delivery records and admin
audit history are durable. Dispatcher pause state, current agent session, agent
heartbeat, rate-limit counters and the short queue cache are process-local.

The application acquires a PostgreSQL session advisory lock at startup and rejects
a second application worker for the same database. The current agent protocol
requires one worker. On restart, dispatch pauses and interrupted jobs become failed,
so staff must inspect the physical print before retrying. This deliberately favors
avoiding duplicate physical prints over automatic retry.

`services/singleton_guard.py` revalidates lock ownership on a five-second watch,
readiness checks and authenticated agent operations. A database reconnect alone
does not restore session locks. After connection loss, the application reacquires
authority before becoming ready, fails uncertain interrupted jobs and leaves
dispatch paused. If another worker owns the lock it does not dispatch jobs.

An asyncio lock serializes agent poll/result/reaper operations. PostgreSQL transaction
advisory locks serialize per-user unpaid uploads and per-order payment/cancellation
workflows. Refund retries reuse a durable provider idempotency key. Queue estimates
are approximate; orders outside the bounded cache use a database aggregate instead
of disappearing from the queue.

Do not increase `--workers` or add replicas until dispatcher leases/heartbeat/pause
state and rate limiting have a tested cross-process design. These can live in the
same PostgreSQL database; microservices are not a prerequisite.

## Adding a feature

1. Define its request/response schema with explicit lengths, numeric bounds and allowed values.
2. Add/change the model only when persistence is necessary.
3. Generate `alembic revision --autogenerate -m "describe_change"`, inspect the SQL and add an explicit downgrade policy.
4. Implement a router and a service when appropriate; authenticate and check ownership before accessing a resource.
5. Record administrative state changes with `record_admin_action` in the business transaction.
6. Register the router in `main.py` and update the relevant runbook.
7. Verify authorization, error cases, migrations and `alembic check` against a separate staging database.

Avoid auto-committing dependencies: a route/service must own the transaction
decision. Avoid implicit lazy loading in async code; load relationships with
`joinedload`/`selectinload` or an explicit awaited refresh.

## Coding conventions

- Python 3.12+; containers use 3.13. Pydantic v2 validation/serialization and SQLAlchemy 2 typed models.
- UTC timestamps in storage; user-facing localization belongs in the frontend.
- Currency amounts are integer rupees locally and integer paise at the provider boundary. Revisit the money model before adding fractional prices or other currencies.
- Log static event names plus safe IDs, not request bodies, passwords, email addresses, cookies or provider payloads.
- Templates use content-hashed asset URLs from `core/assets.py`; relative module imports revalidate instead of silently retaining an older release.
- Preserve existing `detail` error shapes for browser compatibility. Unexpected errors return a generic code and a request ID; validation omits input values.
- JSON schemas are the API contract. Use `textContent` for untrusted browser output and Jinja autoescaping for HTML.
- Test behavior, authorization and failure transitions rather than duplicating implementation details.

## Official references

Guidance checked on 14 October 2026:

- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/) and [deployment concepts](https://fastapi.tiangolo.com/deployment/concepts/).
- [Pydantic settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).
- [SQLAlchemy async sessions](https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html).
- [Alembic asyncio migrations](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic).
- [PostgreSQL backups](https://www.postgresql.org/docs/current/backup.html).
- [Uvicorn resource limits and proxy trust](https://www.uvicorn.org/settings/).
- [Razorpay refund idempotency](https://github.com/razorpay/markdown-docs/blob/master/api/refunds/normal-refunds-idempotent.md).

Runtime dependencies are resolved and pinned in `requirements.lock`. Latest release
numbers alone do not demonstrate compatibility; upgrades must pass regression,
migration and staging checks. PostgreSQL 15 is retained for existing volume
compatibility; a major server upgrade requires its own tested backup/restore or
`pg_upgrade` procedure.
