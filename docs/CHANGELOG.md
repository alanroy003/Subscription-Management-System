# Changelog

## Unreleased
- Step 1: hardened `.gitignore` (generated PDFs, local databases, dumps, credentials), local pre-commit secret scan
  (detect-secrets) that also blocks `.env` files, `.env.example`, `dev.py hooks`, and a `dev.py doctor` that checks `.env`
  names, settings module, pooler type and hook installation without printing values.
- Step 2: ruff + oxlint (`dev.py lint`), `dev.py down`, `dev.py test --pg` (throwaway Postgres container); CI jobs for lint
  and Postgres; concurrency tests (parallel billing runs, discount usage limit 1, gap-free numbering).
- Fix: parallel database helpers now run in-line inside an open transaction (workers could not see uncommitted rows).
- Database integrity: CHECK constraints for money rules; Postgres triggers make issued invoices, their lines and payments
  immutable (status only moves forward); nightly reconciliation (`manage.py reconcile`) with admin email alerts, an
  integrity API and a Data integrity card on the Billing page; database rule violations return 400 instead of 500.
- Audit log: append-only record of sign-ins (and failures), sign-ups, password resets, user and API key changes,
  catalog/tax/discount create-update-delete with field diffs, subscription transitions, invoice confirm/cancel/send,
  payments, billing runs and data checks; actor, channel (web, API key, system) and IP captured automatically; written
  in the same transaction; Postgres trigger blocks edits; doubles as the event outbox; admin Audit log page.
- API docs: Swagger (`/api/docs`) and ReDoc (`/api/redoc`) for the versioned API with a usage guide, grouped
  endpoints, request/response schemas for every operation and Token + API key authorization; schema validated in CI.

## v1.0.0-mvp (2026-10-31)
- Auth: sign-up with server-side password policy, unique email, login/logout, reset link by email, roles Admin / Staff / Customer, admin-only staff creation.
- Catalog: products with variants and price extras, plans with period, minimum quantity, availability and lifecycle options.
- Taxes (GST CGST+SGST / IGST tax groups) and discounts (fixed/percent, minimums, dates, usage limit, scope).
- Quotation templates, subscriptions with numbering, lines, payment terms, lifecycle and timeline.
- Billing engine: idempotent, catch-up, dry run, failure isolation, parallel; invoices with snapshots; confirm/cancel/send/print.
- Payments with partial allocation; paid / outstanding / overdue.
- Customer portal; finance dashboard with MRR, ARPU, churn, renewals and cash forecast, at-risk customers.
- Golden billing regression test and authorization negative tests; CI workflow.
