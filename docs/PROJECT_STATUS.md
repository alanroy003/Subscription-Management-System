# Project status

Release: **v1.1.0, hackathon submission (2026-10-31).** Every scene in the brief is built, tested and demoed.

## Scenes coverage (from the PDF)

| Scene | Built | Proof |
|---|---|---|
| A new customer signs up (unique email, password policy, reset link, roles, admin-only staff) | Yes | `tests/test_auth_and_access.py` |
| Launching a new plan (product, variants +560, period, min qty, dates, close/pause/renew options) | Yes | `test_variant_price_extra`, `test_min_quantity_and_availability_enforced` |
| Turning a quote into a subscription (templates, validity, number, lines, lifecycle, timeline) | Yes | `test_quote_to_active_subscription_bills_first_invoice` |
| Billing day (automatic invoices, taxes, confirm/cancel/send/print, never twice or skipped) | Yes | `test_billing_golden.py`, `test_concurrency_pg.py` |
| A customer asks for a better price (admin-only discounts, limits, auto-apply, stop when out) | Yes | golden test, `test_cancel_releases_discount_usage` |
| The money comes in (method, amount, date, note; paid vs outstanding; overdue) | Yes | golden test, `test_invoice_actions_and_overdue_filter` |
| The finance lead (active, revenue, payments, overdue, filters, summary, < 2 s at scale) | Yes | `reports.summary`; `scripts/perf_check.py` (10k subscriptions, worst p95 1.5 s) |

## Beyond the brief

| Feature | Proof |
|---|---|
| Invoice PDF, attached to emails | `tests/test_invoice_pdf.py` |
| Renewal reminders 30 / 7 / 1 days | `tests/test_renewal_reminders.py` |
| Free trial that converts to a paid plan | `tests/test_free_trial.py` |
| Database-enforced money rules, nightly reconciliation | `tests/test_integrity.py` |
| Append-only audit log, Swagger / ReDoc API docs | `tests/test_audit_and_docs.py` |
| Public API (scoped keys, idempotency, rate limit) | `tests/test_public_api.py` |

Tests: 69 passed + 7 Postgres-only skipped on SQLite; 76 passed on Postgres. CI: lint, both suites, schema, build,
gitleaks.

## Known limits
- SQLite fallback (no `DATABASE_URL`): `seed` fails on the invoice "total adds up" check (float decimals); use Postgres.
- Supabase is in `eu-west-1`: billing actions take 2 to 7 s from India; reads stay under 2 s.
- Docker Compose file is valid but was not run end to end.
