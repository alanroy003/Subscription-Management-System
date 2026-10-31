# MVP plan (time-boxed): decisions and API contract

Mode: BUILD. Owner instruction (2026-10-31 10:07 IST): solo, hard stop 16:30 IST today (~6 h), Claude decides everything else and optimises for a working result.
This replaces the 78 to 103 h step plan. Stage 0B to 0D gates and per-step approval gates are waived by the owner; logged in `docs/APPROVAL_LOG.md`.

## Decisions (each is an ADR-lite; see `docs/adr/0001-time-boxed-mvp.md`)

| # | Decision | Why |
|---|---|---|
| D1 | **Django auth + DRF token auth** instead of Supabase Auth | Removes JWT/JWKS wiring, Admin API calls and the Supabase-mail-cannot-reach-Mailpit problem. Supabase stays as the PostgreSQL host |
| D2 | DB: Supabase Postgres via **session pooler** (`DATABASE_URL`). Tests run on SQLite | Session pooler works on IPv4 and keeps session state; SQLite keeps tests fast and offline |
| D3 | Run natively (`python scripts/dev.py up`), Docker Compose file provided but optional | Docker daemon was not running; native is faster for a 6 h build |
| D4 | Email: Django file backend in dev (`backend/sent_emails/`); SMTP via env if set | Reset link and invoice email visible without extra services |
| D5 | Print/PDF: print-styled invoice page in the browser (Save as PDF) | WeasyPrint needs GTK on Windows; browser print is free and exact |
| D6 | Scheduler: `manage.py run_billing` + "Run billing" button with dry-run; idempotent so it is safe from Windows Task Scheduler | No extra container needed |
| D7 | Authorization in Django querysets + permission classes, negative tests. RLS parked | RLS is a no-op for the `postgres` role; not worth 3 h today |
| D8 | Single currency INR, `Decimal`, per-line half-up rounding to 2 dp, tax-exclusive prices, snapshots on invoice lines | Brief + money rules |
| D9 | GST via tax groups: `gst` mode splits into CGST+SGST (same state as company) or IGST (different state) | Indian GST preset at near-zero cost |
| D10 | Public API keys, webhooks, AI, gateways: parked | Out of time |

## Domain rules

- Variant price = product.sales_price + variant.price_extra (Odoo brand +560).
- Plan = recurrence (daily/weekly/monthly/yearly), price, min_quantity, available_from/to, flags auto_close, closable, pausable, renewable.
- Subscription line unit price defaults to variant price (or product sales price); snapshot, editable while Draft/Quotation.
- Subscription status: draft → quotation → confirmed → active → (paused ↔ active) → closed. Draft/quotation can be cancelled to closed.
  Confirm sets Active immediately when start_date ≤ today; the billing run activates later ones.
- Billing in advance: first invoice at activation for period [start, start+period). `next_invoice_date` advances one period per invoice. Catch-up creates every missed period. Unique (subscription, period_start). Paused subscriptions are skipped and their periods are not billed. Expiry: no period starting on or after expiry_date; auto_close plans close at expiry.
- Discount: fixed or percent; min_amount (on the invoice subtotal) and min_quantity (line quantity); start/end dates; usage_limit (null = unlimited; counted per invoice, released when the invoice is cancelled); scope `all` or `products`. Best single eligible discount per line, applied before tax.
- Tax per line on (line subtotal − discount), each component rounded half-up.
- Invoice status: draft → confirmed → paid; draft/confirmed → cancelled (not if any payment). Confirmed and paid invoices are immutable.
- Due date = invoice_date + payment_term_days. Overdue = confirmed, due_date < today, balance > 0.
- Payment: on a confirmed invoice, 0 < amount ≤ balance; invoice → paid when balance reaches 0.
- MRR = Σ active subscription recurring amount normalised to a month (yearly/12, weekly×52/12, daily×365/12).

## API contract (base `/api`, JSON, auth header `Authorization: Token <key>`)

Pagination: list endpoints return `{count, next, previous, results}`; `?page=N`, page size 25 (`?page_size=` up to 200). Search `?search=`, filters as listed. Errors: `{"detail": "..."}` or `{field: ["msg"]}`. Money fields are strings like `"1234.50"`.

### Auth
- `POST /auth/signup` `{email, password, name}` → `{token, user}` (creates role customer + Customer record)
- `POST /auth/login` `{email, password}` → `{token, user}`
- `POST /auth/logout`
- `GET /auth/me` → `user` = `{id, email, name, role: "admin"|"staff"|"customer", customer_id}`
- `POST /auth/password-reset` `{email}` → 200 always (email contains link `http://localhost:5173/reset-password?uid=..&token=..`)
- `POST /auth/password-reset/confirm` `{uid, token, password}`
- `GET/POST /users` (admin only; POST creates staff `{email, name, password, role:"staff"|"admin"}`)

### Catalog (read: admin+staff; write: admin)
- `/products` `{id, name, type: "service"|"software"|"goods", sales_price, cost_price, notes, tax_group, tax_group_name, is_active, variants:[{id, attribute, value, price_extra, price}]}` (variants writable nested)
- `/plans` `{id, name, product, product_name, price, billing_period: "daily"|"weekly"|"monthly"|"yearly", min_quantity, available_from, available_to, auto_close, closable, pausable, renewable, is_available}`
- `/tax-groups` `{id, name, rate, mode: "gst"|"simple", is_active}`
- `/discounts` `{id, name, kind: "fixed"|"percent", value, min_amount, min_quantity, start_date, end_date, usage_limit, used_count, scope: "all"|"products", products:[ids], is_active}`
- `/quotation-templates` `{id, name, plan, plan_name, validity_days, notes, lines:[{id, product, product_name, variant, quantity}]}` (admin+staff write)
- `/payment-terms` → static list `[{days:0,label:"Immediate"},{15,"Net 15"},{30,...},{45,...}]`

### Customers (admin+staff; customer sees self)
- `/customers` `{id, name, email, phone, address, state, gstin, has_login}` filter none, search name/email

### Subscriptions
- `/subscriptions` list filters `?status=&customer=&plan=&search=` ; item `{id, number, customer, customer_name, plan, plan_name, billing_period, status, start_date, expiry_date, next_invoice_date, payment_term_days, quotation_valid_until, notes, lines:[{id, product, product_name, variant, variant_label, description, quantity, unit_price, tax_group, subtotal}], subtotal, recurring_total, available_actions:[...], events:[{at, from_status, to_status, user_name, note}], created_at}`
- POST/PATCH writable: customer, plan, start_date, expiry_date, payment_term_days, notes, lines (nested replace). Only in draft/quotation.
- `POST /subscriptions/from-template` `{template, customer, start_date}` → subscription (status quotation, quotation_valid_until set)
- `POST /subscriptions/{id}/transition` `{action: "send_quotation"|"confirm"|"activate"|"pause"|"resume"|"close"|"renew", note?}` → subscription. Customers may call `confirm` (accept quotation), `pause`, `resume`, `close`, `renew` on their own, subject to plan flags.

### Invoices
- `/invoices` filters `?status=&customer=&subscription=&overdue=true&date_from=&date_to=&search=`; item `{id, number, subscription, subscription_number, customer, customer_name, customer_snapshot:{name,email,address,state,gstin}, period_start, period_end, invoice_date, due_date, status, currency, subtotal, discount_total, tax_total, total, amount_paid, balance, is_overdue, lines:[{description, quantity, unit_price, subtotal, discount_name, discount_amount, taxes:[{name, rate, amount}], tax_amount, total}], payments:[...], sent_at}`
- `POST /invoices/{id}/confirm|cancel|send` ; `POST /invoices/bulk-confirm` `{ids}`
### Payments
- `/payments` `{id, invoice, invoice_number, customer_name, method: "cash"|"bank_transfer"|"upi"|"card"|"cheque", amount, date, note, created_at}` (POST admin+staff)
### Billing
- `POST /billing/run` `{as_of?: date, dry_run: bool}` → `{id, run_date, dry_run, created, skipped, failed, items:[{subscription_number, period_start, total, status, error}]}`
- `GET /billing/runs` → list of runs (no items)
### Reports (admin+staff)
- `GET /reports/summary?date_from=&date_to=` → `{active_subscriptions, status_counts:{draft,quotation,confirmed,active,paused,closed}, billed, collected, outstanding, overdue_amount, overdue_count, mrr, arpu, churned_last_30, churn_rate, revenue_series:[{month:"2026-05", billed, collected}], renewals:{d30, d60, d90}, forecast:{d30, d60, d90}, at_risk:[{customer_id, customer_name, overdue_count, overdue_amount}], top_overdue:[invoice...]}`
### Docs
- `GET /api/health`, `GET /api/docs` (Swagger), `GET /api/schema`
