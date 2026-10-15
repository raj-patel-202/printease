# Deployment and database upgrades

## What a successful deployment establishes

A working deployment confirms the normal startup and request path for that release.
It does not imply a current fault. The failures to prepare for are later disk/volume
loss, permission changes on an upload mount, failed schema upgrades, expired/rotated
secrets, blocked certificate renewal, and restart during an active print. Keep the
database, upload volume and Caddy certificate data persistent and backed up. Check
renewal and backup failures through your hosting provider's monitoring. Restore a
backup on a disposable host periodically. Local database/app restart and backup
restore drills passed; this does not test your provider's host or DNS configuration.

## New installation

1. Copy `.env.example` to `.env`. Set database and Razorpay credentials and a shared agent token.
2. Generate independent random secrets, for example `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
3. For local development use `docker compose up --build -d`. The `migrate` service completes before the web worker starts.
4. Create the first administrator with `docker compose exec web python create_admin.py`.
5. Open `http://localhost:8000`. Configure the printer using `PRINTER_AGENT.md`.

For an installation outside Docker:

```sh
python -m venv .venv
# Activate using .venv/Scripts/Activate.ps1 on Windows or source .venv/bin/activate on Linux.
python -m pip install -r requirements.lock
# Set DATABASE_URL to the local PostgreSQL host, rather than the Compose host named db.
alembic upgrade head
python create_admin.py
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Do not expose the development server publicly. The default host/origin lists allow
localhost only. `.env` is ignored and excluded from container builds; use environment
injection or the platform's secret facilities on a deployed host.

## Existing database created by the old application

The old server used `metadata.create_all`; that does not upgrade existing tables.
Do not run the baseline creation migration over existing tables, and do not stamp
an unknown schema as current.

1. Stop the old web process and printer dispatch. Back up the database and PDFs; verify a restore in a separate environment.
2. Review `migrations/versions/0001_baseline.py` against the real schema. Run `python scripts/check_baseline.py`; resolve any reported mismatch before continuing.
3. Check case-insensitive duplicates before creating the new unique indexes:

```sql
SELECT lower(username), count(*) FROM users GROUP BY lower(username) HAVING count(*) > 1;
SELECT lower(email), count(*) FROM users GROUP BY lower(email) HAVING count(*) > 1;
SELECT lower(email), count(*) FROM admins GROUP BY lower(email) HAVING count(*) > 1;
```

4. Only after verifying the baseline, run these commands with the application environment:

```sh
alembic stamp 0001_baseline
alembic upgrade head
alembic check
```

For Compose, start only the DB and use `docker compose run --rm --no-deps migrate`
with `python scripts/check_baseline.py`, then `alembic stamp 0001_baseline`, then
`alembic upgrade head` as command overrides. `stamp` records a version and does not
alter schema. The startup check refuses an outdated schema. Existing login cookies
are invalidated by the new required token-version claims.

## Public deployment with HTTPS

Use a Linux host with Docker Compose and a DNS name pointing to it. Set `SITE_DOMAIN`
in `.env`, real payment keys, random secrets and a strong database password. Then:

```sh
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build -d
```

Caddy obtains HTTPS certificates. The overlay enables production mode and Secure
cookies, trusts only the proxy's fixed network address, and sets explicit public
host/origin lists. Ports 80/443 are public; the application port remains bound to
host loopback, and PostgreSQL has no published port. Choose another private subnet
if `172.30.0.0/24` conflicts with your host networks.

Uploads run as container UID/GID 10001. On Linux, provision the bind-mounted
`resource/uploads` directory with write access for that UID. Test a real upload after
deployment. Do not make document directories world-readable. The proxy accepts at
most 22 MB per request, including multipart overhead; update that limit together
with `MAX_FILE_SIZE_MB` if needed.
The edge also bounds header/body/response time and closes oversized rejected streams
before reusing a client connection. Validate those deadlines for your network and
typical PDF sizes.

The default Compose database user is also the database owner. Before operating a
public installation, provision a dedicated runtime role with only SELECT/INSERT/
UPDATE/DELETE on application tables and sequence usage; use an owner role only for
migrations. Supply the migration role's `DATABASE_URL` to the `migrate` service and
the runtime role's URL to `web`. Verify grants after each migration. Restrict UPDATE/
DELETE on `audit_logs` for the runtime role to make the audit trail append-only for
the application. Database administrators can still change it; it is not a
cryptographic tamper-proof ledger.

## Release procedure

1. Review the changes, build and label an image, and deploy it to staging.
2. Verify migrations on a restored representative database, provider test-mode payments/refunds and physical printer behavior.
3. Take a backup. Pause dispatch and drain active prints before stopping the worker.
4. Apply migrations once, start the new worker, check readiness and perform upload/payment/print smoke tests.
5. Resume dispatch deliberately and monitor errors, latency, queue age and storage.

Rollback is a deployment decision: prefer forward fixes for migrations involving
data. Test downgrades on a copy before using them; the baseline downgrade removes
all application tables. Never delete the production database volume to "fix" a
migration. Pin image tags/digests for a recorded release; floating Python/Postgres/
Caddy tags in these starter files need deliberate refreshes and staging validation.
