# Operations runbook

## Logs and health

`docker compose logs -f web` shows structured JSON logs. Each request records method,
route pattern, status, duration and `request_id`. Query strings, raw IDs in URLs,
cookies and bodies are omitted. Exceptions record their type and stack locations,
without potentially secret-bearing exception messages. The API returns `X-Request-ID`
so support can correlate a report with logs. Docker rotates web/database/proxy logs.
Raw Uvicorn access logging stays disabled so query-string receipt tokens do not
appear in a second access log. An interrupted request body is logged as an aborted
request (499), rather than an unexpected 500 error.

`/api/health/live` checks the HTTP process. `/api/health/ready` (also `/api/health`)
requires successful startup and a database query with a short deadline. Readiness
does not check Razorpay or printer connectivity: those are separate dependencies
and should not cause process restart loops. Docker health status does not itself
restart an unhealthy container; configure host monitoring and alerting.

The admin dashboard at `/admin/dashboard` manages printing. `/admin/operations`
lists users, permits access suspension/restoration, shows recent audit records and
reports pool usage, failed prints, payment anomalies and agent connectivity. Its
HTML is only a shell; all data/actions require `CurrentAdmin` authorization.

Administrative API endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/admin/users` | Bounded, paginated user list |
| `PATCH /api/admin/users/{id}/access` | Enable/suspend access, invalidate existing sessions, record an audit event |
| `GET /api/admin/audit` | Paginated administrative history |
| `GET /api/admin/system` | Operational overview without secrets |
| `POST /api/admin/printer/pause` or `/resume` | Control new job dispatch |
| `POST /api/admin/orders/{id}/retry` | Retry a failed paid print after physical inspection |
| `POST /api/admin/orders/{id}/deliver` | Deliver completed print and remove PDF |
| `POST /api/admin/orders/{id}/refund` | Request/retry a refund for a failed/cancelled print |

`size` is 1–100 and `page` is 1–10000. The API-only refund action can be called from
an authenticated same-origin client; financial support staff must review it first.
Normal print queue controls remain in the existing dashboard.

## Suggested alerts to configure on your host

- Readiness failure for more than one minute; container restart or migration failure.
- HTTP 5xx rate above 1% over five minutes; p95 interactive API latency above one second.
- Sustained database pool exhaustion, slow queries, disk usage above 80%, or free upload space below the configured reserve.
- Agent offline while dispatch is enabled; oldest paid pending order beyond the service's wait-time promise.
- `refund_failed`, prolonged `refund_pending`, payment mismatch, failed webhook processing or document cleanup failure.

These are initial operational thresholds, not measured service guarantees. The code
emits the signals but does not install an external log collector, paging service or
monitoring account. Set ownership and notification destinations before public use.

## Payment and printer incidents

A provider timeout has an ambiguous outcome. Reuse the stored refund idempotency
key; do not issue a new refund manually without reconciling the provider record.
Subscribe Razorpay to `payment.captured`, `refund.processed`, and `refund.failed` at
`https://YOUR_DOMAIN/api/payments/webhook`. Signatures are verified before parsing
and supported event deliveries are recorded for retry/deduplication.

Payment verification checks currency, amount, capture state and provider order.
An amount discrepancy fails printing and attempts a refund. A capture arriving
after cancellation attempts a refund. Pending refunds remain pending until a
processed provider response or signed event confirms completion. Review old pending
and partial refunds against the provider. Partial refund events do not mark an
entire order refunded; they retain a pending review state and prevent reprinting.
Captured amounts are stored in minor units for refund comparison. Legacy payments
without captured amounts fall back to the order amount and need manual
reconciliation if their original capture differed from it. Review pending
and failed refunds against Razorpay; there is no scheduled reconciliation worker.
Provider calls and database commits cannot form one atomic transaction.

After a server restart, interrupted prints are failed and dispatch stays paused.
Inspect the printer/spooler before retrying: the agent may have printed even when
the response was lost. A job timeout is also not proof that nothing printed.

When a delivered/cancelled PDF cannot be deleted, inspect the correlated cleanup log
and retry deletion manually after confirming the terminal status. Database changes
and filesystem deletion are not atomic. Do not remove active documents.

## Backup and recovery

Define recovery targets with the business (for example RPO one hour and RTO two
hours) and prove them with restore drills. Those values are objectives, not current
guarantees. Back up both PostgreSQL and the upload directory, encrypt copies, store
at least one copy off the application host, and restrict access to document backups.

Example commands work on Windows and Linux without piping binary dumps through
PowerShell:

```sh
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/printease.dump'
docker compose cp db:/tmp/printease.dump ./printease.dump
docker compose exec -T db rm /tmp/printease.dump
```

Use a timestamped destination for each backup. Copy the PDF directory while uploads
and printing are paused if a consistent filesystem/database snapshot is required.
For tighter recovery targets use PostgreSQL base backups plus WAL archiving, managed
by your database platform. A Docker volume is persistence, not a backup.

Restore only into a separate empty database first. Copy the dump into its container
and use `pg_restore --exit-on-error` with that database's credentials. Run migrations,
compare user/order counts, test a stored PDF and provider test-mode flow, and record
the restore duration. Never test recovery by overwriting the only live database.

Order record retention prevents self-service deletion from cascading through
payments, including unpaid/cancelled orders that can receive a late provider capture.
Accounts with any order history require support-assisted closure. Support must follow an explicit account-closure/anonymization
policy. Choose retention periods for PDFs, audit logs, webhook payloads and backups;
webhook payloads can contain personal information. There is no automatic purge job.

## Dependency maintenance

`requirements.txt` lists direct dependencies; `requirements.lock` pins resolved runtime
dependencies. Refresh in a clean maintenance environment,
review official release notes, resolve the complete runtime dependency graph, update
both direct pins and lock, and verify the release in staging. Do not replace the lock with a
freeze from an environment containing unrelated development packages.

Before releasing dependency updates, check PostgreSQL migrations/schema drift,
runtime dependency advisories and the container build, and exercise the main user
journeys in staging. A clean advisory check is time-sensitive and does not
substitute for application security review. Development tools and CI are not
included in this deployment repository.
