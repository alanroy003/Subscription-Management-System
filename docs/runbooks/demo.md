# Demo script (about 7 minutes)

Before: `python scripts/dev.py seed --reset`, then `python scripts/dev.py up`. Open http://localhost:5173/login.
Logins: `admin@brightloop.test`, `staff@brightloop.test`, `customer@brightloop.test`; `DEMO_PASSWORD` in `.env` (or
the seed default in `backend/core/management/commands/seed.py`) signs in all three. Emails land in `backend/sent_emails/`.

1. **Sign-up and free trial (45 s).** `/signup`: a weak password fails the live checklist and the server. A strong one
   lands in the portal with a **30-day free trial already running** and a 0 invoice marked Paid. Signing up again with
   the same email says "already exists".
2. **Admin sets up (60 s).** As admin: Products → *Brightloop CRM*, variant *Brand: Odoo* +560. Plans → *CRM Monthly*
   and *Free Trial (30 days)* (trial toggle). Discounts → *Volume 10% (5+ seats)*. Users → add staff (admin only).
3. **Quote to subscription (60 s).** As staff: Subscriptions → New → *From quotation template* → *CRM Starter (Odoo)*
   for *Acme Traders* → Quotation, valid 30 days → **Confirm** → Active; the timeline shows each step and the first
   invoice already exists.
4. **Billing day (45 s).** Billing runs → **Dry run** (8 due, nothing saved) → **Run now** (8 invoices) → **Run now**
   again (0: never billed twice). The *Data integrity* card says all figures reconcile.
5. **Invoice, PDF and payment (60 s).** Open a new invoice: discount and CGST/SGST (IGST out of state). **Confirm** →
   **Download PDF** → **Send by email** (PDF attached). Record a partial payment, then the rest → **Paid**.
6. **Renewals (30 s).** Dashboard → *Upcoming renewals*: countdowns and 30d / 7d / 1d badges → **Send due reminders**
   → badges fill in; press again → nothing resent. The reminder shows on the subscription timeline.
7. **Finance lead (30 s).** Dashboard KPIs (MRR, ARPU, churn, billed vs collected, overdue, forecast, at-risk); switch
   the date range.
8. **Customer portal (45 s).** As `customer@brightloop.test`: only Acme's data. Banner → **Start free trial** → 30 days
   left → **Choose a plan** → *CRM Monthly* → a paid subscription starting the day the trial ends. Download an invoice
   PDF; pause a monthly plan.
9. **Trust and integration (30 s).** Admin → *Audit log* (every action above, who, how, from where). *API docs*
   (Swagger) → Authorize with an API key → `GET /api/v1/invoices`.

Recovery: `python scripts/dev.py seed --reset` rebuilds the demo data in about 20 seconds.
