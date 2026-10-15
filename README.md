# PrintEase

A college-campus printing service built as a modular monolith: one FastAPI
application, one PostgreSQL database and persistent PDF storage. The Windows
printer agent pulls authorized jobs. An optional Caddy proxy provides HTTPS.

## Start here

- [Architecture and contributor guide](docs/ARCHITECTURE.md)
- [Installation, HTTPS and database migrations](docs/DEPLOYMENT.md)
- [Logs, admin controls, incidents and backups](docs/OPERATIONS.md)
- [Razorpay setup and payment recovery](docs/PAYMENTS.md)
- [Campus capacity planning](docs/PERFORMANCE.md)
- [Security boundaries](docs/SECURITY.md)
- [Windows printer agent](docs/PRINTER_AGENT.md)
- [What belongs on GitHub](docs/REPOSITORY.md)

## Installation

Requires Docker Compose, or Python 3.12+ and PostgreSQL. Containers use Python 3.13.

1. Copy `.env.example` to `.env` and set your database, provider and agent secrets.
2. For a **new empty database**, run `docker compose up --build -d`.
3. Run `docker compose exec web python create_admin.py` to create an administrator.
4. Open `http://localhost:8000` and configure the Windows printer agent.

**Existing databases must follow the baseline verification and migration procedure
in the deployment guide before starting this version.** Do not recreate an existing
database. Application startup checks its migration version.

For installation outside Docker, create and activate a virtual environment, install
`requirements.lock`, set `DATABASE_URL`, run `alembic upgrade head`, and start
`uvicorn main:app --host 127.0.0.1 --port 8000`.

For a public HTTPS deployment, configure `SITE_DOMAIN` and follow the production
Compose instructions in the deployment guide.

## Project capabilities

- Typed production settings, explicit host/origin checks and Secure cookies.
- Argon2 authentication, user/admin roles, session revocation and password changes.
- Authorized PDF access, size/page limits and free-storage checks.
- Request IDs, JSON logs, safe error responses and liveness/readiness endpoints.
- Bounded pagination, connection pools and versioned Alembic migrations.
- Admin print controls at `/admin/dashboard`; users, audit and system status at `/admin/operations`.
- Payment matching, refund idempotency and signed capture/refund callbacks.
- Serialized printer claims, interrupted-print recovery and a single-worker guard.
- Non-root application container, rotating logs and optional HTTPS proxy.

## Repository and deployment

`requirements.txt` records direct dependencies; `requirements.lock` pins the
resolved production dependencies used by Docker. `pyproject.toml` contains project
metadata. Development tools, test fixtures, load drivers and CI are not included.

Keep migrations, `scripts/check_baseline.py`, templates, static assets and the
vendored PDF.js resources in GitHub. `scripts/update_pdfjs.py` maintains the pinned
browser renderer and verifies downloaded package integrity.

Keep real secrets, uploaded documents, database files/dumps, local virtual
environments and generated output outside GitHub. `.gitignore` and `.dockerignore`
define those exclusions. Commit `.env.example` with placeholders only.

The campus target is up to approximately 10,000 print requests per day. Printing
speed, pages per job, pickup handling and disk capacity still need operational
monitoring. Keep **one application worker** until printer coordination and rate
limits support multiple processes. See the performance and security guides for
capacity assumptions and remaining boundaries.
