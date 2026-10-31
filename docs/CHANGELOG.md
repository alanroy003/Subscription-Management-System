# Changelog

## v1.0.0-mvp (2026-10-31)
- Auth: sign-up with server-side password policy, unique email, login/logout, reset link by email, roles Admin / Staff / Customer, admin-only staff creation.
- Catalog: products with variants and price extras, plans with period, minimum quantity, availability and lifecycle options.
- Taxes (GST CGST+SGST / IGST tax groups) and discounts (fixed/percent, minimums, dates, usage limit, scope).
- Quotation templates, subscriptions with numbering, lines, payment terms, lifecycle and timeline.
- Billing engine: idempotent, catch-up, dry run, failure isolation, parallel; invoices with snapshots; confirm/cancel/send/print.
- Payments with partial allocation; paid / outstanding / overdue.
- Customer portal; finance dashboard with MRR, ARPU, churn, renewals and cash forecast, at-risk customers.
- Golden billing regression test and authorization negative tests; CI workflow.
