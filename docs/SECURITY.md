# Security boundaries

Users authenticate with Argon2 password hashes and short-lived HttpOnly cookies.
User/admin tokens have separate role claims. Token versions are checked against the
database on every authenticated request. Logout and password changes revoke all
sessions for that identity; access suspension/restoration invalidates user sessions.
Old cookies without the new required version claims are rejected.

Cookie mutations require a trusted Origin/Referer in production, including login.
Provider callbacks authenticate signed payloads and are exempt from origin checks;
the printer protocol authenticates its bearer secret. These exemptions must remain
limited to those independent authentication mechanisms. The deployment proxy must
preserve browser Origin/Referer headers.

Production configuration requires Secure cookies, explicit hosts, HTTPS origins and
non-placeholder signing/agent/webhook secrets. Documentation/OpenAPI routes are
disabled in production. The deployment uses TLS and trusts forwarding headers only
from the edge proxy. Local development permits requests without Origin, but rejects
an explicitly untrusted origin.

Documents require user ownership or administrator authorization. Agent downloads
require the currently assigned agent session. Stored filenames are randomized PDFs
and validated against traversal when computing a path. PDFs have actual byte/page
checks; encrypted and invalid documents are rejected. pypdf validation does not
remove embedded scripts/attachments or prove that a PDF is safe for a printer.
For hostile public uploads, test an isolated parser/rendering process with CPU,
memory and execution deadlines and a document scanning policy before public launch.
That isolation is not implemented here.

The current administrator role has full operational access. Create individual admin
accounts, avoid shared credentials and restrict the admin surface by network policy
where possible. This implementation does not include MFA, an external identity
provider, delegated permission tiers, email verification or email-based password
recovery. Choose those controls based on the actual public deployment requirements;
do not describe them as implemented.

Do not log credentials or bodies. Audit records intentionally contain safe actor/
target IDs and action names. Webhook payloads are stored in the database for delivery
processing and can contain personal data; restrict DB/backup access and define a
purge policy. Runtime DB privileges should prevent audit updates/deletes.

Rate limits are per process and client IP. Shared-network users can share a limit,
and restart resets counters. Enforce infrastructure protections for abusive public
traffic; do not remove authentication throttles to make a benchmark look better.

Secrets stay outside source control. Rotate signing/agent/provider keys if exposed,
and coordinate agent token changes with the physical printer PC. Set database
network/role restrictions and backup encryption on the deployed environment.

The changes add security controls; they are not an independent penetration test
or a compliance certification. The deployment repository does not include the
development test suite or CI workflow.

The bundled browser PDF renderer is Mozilla PDF.js 6.4.299. The module, matching
worker, fonts, CMaps and WASM resources are served locally. Scripting/eval/XFA are
disabled for canvas previews. `scripts/update_pdfjs.py` verifies the npm registry's
SHA-512 package integrity before vendoring files and records a SHA-256 manifest.
Update this package separately from Python dependencies: Python advisory tools
cannot audit vendored JavaScript. The previous 3.11.174 renderer already disabled
eval, mitigating CVE-2024-4367, but was outdated and has been replaced.

Before deployment, authorization, JWT, CSRF, upload and signed-webhook checks and
a Python static security scan passed. Those development tools were removed from
this repository at the owner's request. A previous clean scan does not establish
the absence of vulnerabilities or replace security review of future changes.
