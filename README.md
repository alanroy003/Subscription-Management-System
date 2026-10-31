# Brightloop Subscription Management System

One system for products, plans, quotations, subscriptions, recurring invoices, discounts, GST, payments, a customer
portal and finance reporting. Built for the "Subscription Management System" problem statement
(`docs/00-inputs/Subscription_Management_System.pdf`).

**Stack:** React + TypeScript + Vite · Django 5 + Django REST Framework · Supabase PostgreSQL (session pooler) ·
GitHub Actions. Architecture decisions: [`docs/adr/0001-time-boxed-mvp.md`](docs/adr/0001-time-boxed-mvp.md).

## Quick start (Windows PowerShell, Python 3.11+, Node 20+)

```powershell
python scripts/dev.py setup      # backend venv + pip install, frontend npm install, git secret-scan hook
python scripts/dev.py doctor     # checks tools, .env and the database connection
python scripts/dev.py migrate
python scripts/dev.py seed --reset
python scripts/dev.py up         # API http://127.0.0.1:8000/api/docs  ·  App http://localhost:5173
```

`.env` lives in the repo root and is never committed; copy `.env.example` (names only) to start. Every manual
commit runs a local secret scan (detect-secrets) that blocks keys and `.env` files. Required: `DATABASE_URL` (Supabase **session pooler**,
port 5432) and `DJANGO_SECRET_KEY`. Optional: `DEMO_PASSWORD`, `EMAIL_HOST`/`EMAIL_PORT` (e.g. Mailpit), `COMPANY_STATE`.
Without `DATABASE_URL` the backend falls back to a local SQLite file.

**Demo logins** (local seed data): `admin@brightloop.test`, `staff@brightloop.test`, `customer@brightloop.test`, all
with the password in `DEMO_PASSWORD` or the seed default in `backend/core/management/commands/seed.py`.

Emails (password reset, invoices) are written to `backend/sent_emails/` unless `EMAIL_HOST` is set.

## What it does

| Scene in the brief | Where |
|---|---|
| Sign-up, password policy, reset link, roles (Admin / Staff / Customer), only admin adds staff | `/signup`, `/forgot-password`, Users page · `backend/accounts/` |
| Products with variants and price extras (Odoo brand +560), plans with period, min quantity, availability, auto-close / closable / pausable / renewable | Products, Plans pages |
| Quotation templates with validity → subscription with number, lines, payment terms; Draft → Quotation → Confirmed → Active → Paused / Closed with a timeline | Templates, Subscriptions pages |
| Billing day: invoices generated from subscriptions, GST (CGST+SGST or IGST by place of supply), discounts applied, never twice (unique subscription + period), catch-up, dry run, failure isolation | Billing page · `python scripts/dev.py billing` |
| Invoice PDF: server-rendered tax invoice with GST breakdown, downloadable by staff and customers, attached to every invoice email | Invoice page → **Download PDF** · `GET /api/v1/invoices/{id}/pdf` |
| Renewal reminders: emails 30, 7 and 1 day before expiry, each sent once, shown on the subscription timeline | Dashboard → **Upcoming renewals** → Send due reminders · runs daily · `python backend/manage.py send_renewal_reminders` |
| Discounts: admin only, fixed or %, minimum amount or quantity, dates, usage limit, product or whole-subscription scope | Discounts page |
| Payments: method, amount, date, note; partial payments; paid / outstanding / overdue | Invoice detail, Payments, Invoices → Overdue |
| Finance lead: active subscriptions, billed, collected, outstanding, overdue, MRR, ARPU, churn, renewals and 30/60/90-day cash forecast, at-risk customers, filters | Dashboard |
| Customer portal: own subscriptions and invoices only, download PDF / print, accept quotation, pause / resume / close / renew where the plan allows | Log in as the customer |

## Quality

```powershell
python scripts/dev.py test       # pytest (golden billing regression, auth and isolation negative tests) + frontend build
python scripts/dev.py test --pg  # also runs the Postgres-only concurrency tests in a throwaway docker container
python scripts/dev.py lint       # ruff + oxlint
python scripts/dev.py perf       # times every main endpoint against the configured database
```

- Money is `Decimal` only, rounded half-up to 2 dp per line and tax component; invoices store tax and discount snapshots;
  confirmed invoices are immutable.
- Scale test against Supabase `eu-west-1` (~210 ms per round trip from the dev machine) with **10,000 subscriptions,
  75,428 invoices, 104,879 invoice lines and 67,437 payments** (`seed --reset --subs 10000`): every endpoint p95 under
  1.6 s, dashboard summary p95 0.8 s (`python scripts/dev.py perf`). Write actions that bill (confirm, billing run) take
  2 to 10 s because every statement crosses the ocean; a Supabase project in `ap-south-1` (Mumbai) would cut that ~5x.
- The database itself enforces the money rules (CHECK constraints) and freezes issued invoices and payments (triggers);
  a nightly `python backend/manage.py reconcile` re-adds every total and alerts admins on any mismatch.
- Every sensitive action (sign-ins, staff and API key changes, catalog edits, invoices, payments, billing runs) is
  written to an append-only audit log in the same transaction; admins browse it on *Settings → Audit log*.
- RLS is enabled on all public tables so the Supabase Data API cannot read business data with the publishable key.

## Public API

Full reference: **Swagger** at http://127.0.0.1:8000/api/docs and **ReDoc** at http://127.0.0.1:8000/api/redoc (also
linked as *API docs* in the admin sidebar), with a usage guide, every endpoint grouped by area, request and response
schemas, and an Authorize button for both a login token and an API key.

Admins create keys on **API keys** (hashed at rest, scoped `read` / `write`, revocable, shown once). Call any endpoint
under `/api/v1/` with `X-API-Key: <key>`; add `Idempotency-Key: <unique id>` to POSTs so retries replay the first
response instead of creating duplicates. Rate limit: 120 requests/min per key (`API_KEY_RATE`). Interactive docs with
the full schema: http://127.0.0.1:8000/api/docs.

```bash
curl -H "X-API-Key: $KEY" http://127.0.0.1:8000/api/v1/invoices?overdue=true
```

## Docker (optional)

`docker compose up --build` runs the API, the web app, a daily billing scheduler (`backend/scheduler.py`, 02:00 IST,
idempotent catch-up) and Mailpit (http://localhost:8025) for emails. It uses the same `.env`.

Docs: [`docs/01-planning/mvp-plan.md`](docs/01-planning/mvp-plan.md) (domain rules, API contract) ·
[`docs/runbooks/demo.md`](docs/runbooks/demo.md) (5-minute demo) · [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).
