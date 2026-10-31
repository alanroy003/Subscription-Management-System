# Project status

Mode: BUILD (time-boxed MVP, gates waived by the owner, see `APPROVAL_LOG.md`). Deadline 2026-10-31 16:30 IST.

## Scenes coverage (from the PDF)

| Scene | Built | Proof |
|---|---|---|
| A new customer signs up (unique email, password policy, reset link, roles, admin-only staff) | Yes | `tests/test_auth_and_access.py` |
| Launching a new plan (product, variants +560, plan period/min qty/dates/options) | Yes | `test_variant_price_extra`, `test_min_quantity_and_availability_enforced` |
| Turning a quote into a subscription (templates, validity, number, lines, lifecycle, timeline) | Yes | `test_quote_to_active_subscription_bills_first_invoice` |
| Billing day (auto invoices, taxes, confirm/cancel/send/print, never twice or skipped) | Yes | `test_golden_billing_month`, `test_dry_run_changes_nothing`, `test_failure_isolation` |
| A customer asks for a better price (admin-only discounts, limits, auto-apply, stop when out) | Yes | golden test (limit 2 exhausted on cycle 3), `test_cancel_releases_discount_usage` |
| The money comes in (method, amount, date, note; paid vs outstanding; overdue) | Yes | golden test, `test_invoice_actions_and_overdue_filter` |
| The finance lead (active, revenue, payments, overdue, filters, summary, < 2 s) | Yes | `reports.summary`; `scripts/perf_check.py` at 10k subscriptions / 75k invoices: worst p95 1.5 s |
| Wow Pack: public API (hashed scoped revocable keys, /api/v1, idempotency, rate limit), GST presets, MRR/ARPU/churn, 30/60/90 forecast, at-risk list | Yes | `tests/test_public_api.py`, dashboard |

## Now / Next / Blocked
- Done: every PDF scene works end to end in the browser against Supabase (staff, admin, customer portal).
- Next (optional): verify Docker Compose once Docker Desktop runs; move Supabase to ap-south-1 for faster writes.
- Blocked: `gh` not authenticated (no PRs or GitHub board).

## Top risks
1. Supabase latency (~210 ms per query): mitigated by pooled connections, parallel aggregates, lean list queries.
2. Tests run on SQLite: Postgres-only behaviour (row locks under concurrency) is not exercised.
