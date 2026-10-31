# ADR 0001: Time-boxed MVP architecture

Status: Accepted (2026-10-31). Decided by Claude under the owner's delegation ("you can decide ... I want an optimised result").

## Context
Solo build, hard stop 16:30 IST on 2026-10-31 (about 6 h). The original plan needed 78 to 103 h. The PDF scenes are the
core objective. Environment findings: Supabase DEV is in `eu-west-1` (~210 ms per query from the dev machine), Docker
daemon not running, `gh` not authenticated.

## Options
1. Original stack in full (Supabase Auth + JWT, RLS policies, Docker Compose, Mailpit, WeasyPrint, scheduler container).
2. Same stack minus the parts that cost hours but add no visible behaviour for the scenes.

## Decision
Option 2:

| Area | Decision | Trade-off |
|---|---|---|
| Auth | Django auth (email as username) + DRF token auth; policy enforced server-side; reset link via Django email | Supabase Auth unused. Removes JWT/JWKS wiring and the "Supabase mail cannot reach local Mailpit" problem |
| Database | Supabase Postgres, **session pooler** (`DATABASE_URL`, port 5432), psycopg 3 client pool (`OPTIONS.pool`, 4 to 12) | The transaction pooler (6543) is not used: Django needs session state |
| Latency | Read endpoints are 2 to 4 queries; dashboard runs 9 aggregates in parallel; billing run bills subscriptions in parallel, each in its own transaction | At 10k subscriptions / 75k invoices every endpoint p95 is under 1.6 s (`scripts/perf_check.py`) |
| RLS | Enabled on every public table with no policies (migration `core/0002`), so the Supabase Data API with the publishable key sees nothing. Django (table owner) is not restricted; customer isolation is enforced in querysets with negative tests | Not per-customer RLS policies |
| Scheduler | `manage.py run_billing` + "Run billing" button with dry run; `scheduler` service in Docker Compose runs it daily | Plain loop, no Postgres advisory lock: run one scheduler only (billing is idempotent anyway) |
| Email | SMTP if `EMAIL_HOST` is set (Mailpit), else files in `backend/sent_emails/` | |
| Print/PDF | Print-styled invoice page in the browser (Save as PDF) | No WeasyPrint/GTK on Windows |
| Tests | pytest on SQLite (offline, fast) | Postgres-only behaviour (row locks) is not exercised in tests |
| Money | `Decimal`, half-up to 2 dp per tax component and line, snapshots on invoice lines, unique `(subscription, period_start)` | |
| Numbering | Gap-free per year via a locked `Sequence` row, taken last in the invoice transaction | |

## Consequences
- Phase 2 can still add Supabase Auth by mapping JWT `sub` to `User`; the domain does not depend on the auth provider.
- Public API keys, idempotency and rate limits were added after the core (Wow Pack). Webhooks and AI are parked.

## Links
`docs/01-planning/mvp-plan.md` (rules and API contract), `backend/core/services.py`, `backend/core/pricing.py`.
