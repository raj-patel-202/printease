# Razorpay payment operations

The application creates Orders on the server, calculates prices from validated PDF
pages and server-side rates, verifies Checkout signatures, and fetches provider
payment/order details before accepting browser confirmation. Only a captured payment
can enter the print queue. An `authorized` response remains processing.

## Required dashboard settings

Enable **Auto-capture all payments** in the intended Razorpay account/mode. This
application relies on automatic capture; it does not run a manual capture worker.
Register the public HTTPS `/api/payments/webhook` endpoint and subscribe to
`payment.captured`, `refund.processed` and `refund.failed`. Its signing secret must
match `RAZORPAY_WEBHOOK_SECRET`. Test-mode and live-mode keys/settings are separate.
Configure the webhook alert email and check delivery failures after each release.

Duplicate callbacks are expected. Events are recorded by provider event ID and
financial changes serialize on a PostgreSQL order lock. Completed refunds cannot
be regressed by a later failed event. Processing failures return non-2xx so the
provider can retry; receiving a request is not treated as successfully processing it.
The handler can exceed the provider's five-second acknowledgement window during
slow provider calls, so retries must remain safe. No background broker is required.

Refund requests persist a UUID idempotency key before making the provider request.
Retries use the same header and request body. Pending is not reported as processed;
partial or excessive amounts require review. A timeout is an uncertain outcome,
not proof that the provider did nothing. Check the existing refund before deciding
to initiate another one. Never clear its idempotency key merely to retry.

## Failure and recovery

If a user closes Checkout, loses connectivity or a webhook is delayed, preserve the
order/payment link. A capture arriving after local cancellation triggers a refund.
Use the operations dashboard to inspect payment anomalies; compare provider IDs
and captured/refunded minor-unit amounts with Razorpay before taking action.

Razorpay retries failed webhooks for 24 hours and can then disable the endpoint.
After an extended outage, fix the endpoint, re-enable it in the Dashboard and
reconcile missed transactions against provider records. Scheduled reconciliation
is not implemented. When rotating webhook secrets, arrange a maintenance window
or retain an overlap verifier externally: old deliveries are signed with the old
secret, and this application currently accepts one secret at a time.

An API response or local simulation cannot prove that funds reached a bank account.
Provider/bank settlement is monitored in Razorpay. Automated tests use fake HTTP
provider responses and genuine HMAC verification; no live-money load tests run.

## Official references reviewed on 15 October 2026

- [Python Checkout integration](https://razorpay.com/docs/server-integration/python/test-app/)
- [Capture settings](https://github.com/razorpay/markdown-docs/blob/master/payments/payments/capture-settings.md)
- [Webhook best practices](https://github.com/razorpay/markdown-docs/blob/master/webhooks/best-practices.md)
- [Signature validation, duplicates and ordering](https://github.com/razorpay/markdown-docs/blob/master/webhooks/validate-test.md)
- [Idempotent refunds](https://github.com/razorpay/markdown-docs/blob/master/api/refunds/normal-refunds-idempotent.md)
