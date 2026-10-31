# Changelog

## v1.1.0 (2026-10-31, hackathon submission)
- Free trial: plans can be marked as a free trial (price 0, length in days); new sign-ups get it automatically
  (`TRIAL_ON_SIGNUP`), customers can start it from the portal and staff for any customer; one trial per customer,
  enforced everywhere; its 0 invoice is settled at once; it closes itself; Convert to paid plan creates the paid
  subscription starting when the trial ends. Invoice periods now stop at the expiry date. `GET /api/v1/trial`,
  `POST /api/v1/trial/start`, `POST /api/v1/subscriptions/{id}/convert`.
- Renewal reminders: emails 30, 7 and 1 day before a subscription expires (customer, admins copied; team only if the
  customer has no email), each sent once per expiry date, only the most urgent after missed days, fresh set after
  renewal; timeline and audit entries; daily via the scheduler or `manage.py send_renewal_reminders`; Upcoming
  renewals card on the dashboard with a Send due reminders button; `GET /api/v1/renewals`.
- Invoice PDF: server-rendered tax invoice (GST breakdown, place of supply, payments, balance, Indian digit grouping)
  from the invoice's stored snapshot; `GET /api/v1/invoices/{id}/pdf` (customers: own issued invoices only; staff can
  preview drafts); attached automatically to invoice emails; Download PDF button for staff and in the customer portal.
- Step 1: hardened `.gitignore` (generated PDFs, local databases, dumps, credentials), local pre-commit secret scan
  (detect-secrets) that also blocks `.env` files, `.env.example`, `dev.py hooks`, and a `dev.py doctor` that checks `.env`
  names, settings module, pooler type and hook installation without printing values.
- Step 2: ruff + oxlint (`dev.py lint`), `dev.py down`, `dev.py test --pg` (throwaway Postgres container); CI jobs for lint
  and Postgres; concurrency tests (parallel billing runs, discount usage limit 1, gap-free numbering).
- Fix: parallel database helpers now run in-line inside an open transaction (workers could not see uncommitted rows).
- Database integrity: CHECK constraints for money rules; Postgres triggers make issued invoices, their lines and payments
  immutable (status only moves forward); nightly reconciliation (`manage.py reconcile`) with admin email alerts, an
  integrity API and a Data integrity card on the Billing page; database rule violations return 400 instead of 500.
- Audit log: append-only record of sign-ins (and failures), sign-ups, password resets, user changes, issued and
  revoked access keys, catalog, tax and discount edits with field diffs, subscription transitions, invoice confirm,
  cancel and send, payments, billing runs and data checks; actor, channel (web, API key, system) and IP captured automatically; written
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
