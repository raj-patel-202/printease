# GitHub contents and local-only files

Commit application source, migrations, templates/static assets, pinned production
dependencies, Docker/HTTPS configuration, operator documentation and `.env.example`.
The Windows printer agent belongs in the repository; Docker excludes it from the
server image because it runs on the printer PC.

Keep these files local; `.gitignore` excludes them:

| Local content | Purpose |
| --- | --- |
| `.env` and other real environment files | Database, payment, signing and printer-agent secrets |
| `printer-pc/agent_config.json` | The printer PC's server address and private agent token; commit the example instead |
| `.venv/`, `venv/`, `env/` | Locally installed Python packages |
| `__pycache__/`, tool caches and coverage output | Generated development output |
| `resource/uploads/` | Private customer PDFs |
| Database files, dumps, `backups/`, PostgreSQL/Caddy data directories | Persistent data and recovery material |
| `logs/`, temporary files and IDE settings | Host-specific runtime/development output |
| Private keys, credential JSON, `.aws/`, `.codex/`, `.agents/` | Local credentials and machine configuration |

Production data must live on persistent storage and be backed up separately.
GitHub is not a database/PDF backup. Keep `.env.example` limited to placeholders.
Never place real secrets in source, documentation, screenshots or Git commands.

Before your first push, run `git status --short` after staging and review the file
list. Use `git check-ignore -v .env resource/uploads/example.pdf` to verify the main
exclusions. Ignore rules do not remove files that were already committed: if that
has happened, remove them from tracking, address repository history as needed and
rotate exposed credentials.

Test suites, disposable validation stacks, CI workflows and development-tool
configuration were removed at the owner's request. They are not part of this
repository. Database migrations and the read-only baseline checker remain because
they are required for safe installation and upgrades.
