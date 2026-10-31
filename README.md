# Brightloop Subscription Management System

One system for products, plans, quotations, subscriptions, recurring invoices, discounts, GST, payments, a customer
portal and finance reporting. Built for the "Subscription Management System" problem statement
(`docs/00-inputs/Subscription_Management_System.pdf`).

**Stack:** React + TypeScript + Vite · Django 5 + Django REST Framework · Supabase PostgreSQL (session pooler) ·
GitHub Actions. Architecture decisions: [`docs/adr/0001-time-boxed-mvp.md`](docs/adr/0001-time-boxed-mvp.md).

## Quick start (Windows PowerShell, Python 3.11+, Node 20+)

```powershell
python scripts/dev.py setup      # backend venv + pip install, frontend npm install
python scripts/dev.py doctor     # checks tools, .env and the database connection
python scripts/dev.py migrate
python scripts/dev.py seed --reset
python scripts/dev.py up         # API http://127.0.0.1:8000/api/docs  ·  App http://localhost:5173
```

`.env` lives in the repo root and is never committed. Required: `DATABASE_URL` (Supabase **session pooler**,
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
| Discounts: admin only, fixed or %, minimum amount or quantity, dates, usage limit, product or whole-subscription scope | Discounts page |
| Payments: method, amount, date, note; partial payments; paid / outstanding / overdue | Invoice detail, Payments, Invoices → Overdue |
| Finance lead: active subscriptions, billed, collected, outstanding, overdue, MRR, ARPU, churn, renewals and 30/60/90-day cash forecast, at-risk customers, filters | Dashboard |
| Customer portal: own subscriptions and invoices only, print / save PDF, accept quotation, pause / resume / close / renew where the plan allows | Log in as the customer |

## Quality

```powershell
python scripts/dev.py test       # pytest (golden billing regression, auth and isolation negative tests) + frontend build
python scripts/dev.py perf       # times every main endpoint against the configured database
```

- Money is `Decimal` only, rounded half-up to 2 dp per line and tax component; invoices store tax and discount snapshots;
  confirmed invoices are immutable.
- Measured against Supabase `eu-west-1` (~210 ms per round trip from the dev machine): every endpoint p95 under ~1.1 s.
- RLS is enabled on all public tables so the Supabase Data API cannot read business data with the publishable key.

Docs: [`docs/01-planning/mvp-plan.md`](docs/01-planning/mvp-plan.md) (domain rules, API contract) ·
[`docs/runbooks/demo.md`](docs/runbooks/demo.md) (5-minute demo) · [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).
