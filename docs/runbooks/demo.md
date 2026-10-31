# Demo script (about 5 minutes)

Before: `python scripts/dev.py seed --reset`, then `python scripts/dev.py up`. Open http://localhost:5173.

1. **Sign-up (30 s).** `/signup`: try `password` → the live checklist and the server reject it. Use a strong one →
   lands in the customer portal. Sign up again with the same email → "already exists".
2. **Admin sets up (60 s).** Log in as `admin@brightloop.test`. Products → *Brightloop CRM*: variant *Brand: Odoo*
   +560 (price 1,560). Plans → *CRM Monthly*: monthly, pausable, renewable. Discounts → *Volume 10% (5+ seats)*,
   usage count visible. Users → add a staff member (only the admin sees this page).
3. **Quote to subscription (60 s).** Log in as `staff@brightloop.test`. Subscriptions → New → from template
   *CRM Starter (Odoo)* for *Acme Traders* → status Quotation, valid 30 days. Confirm → Active; timeline shows each
   step; the first invoice exists already (billing in advance).
4. **Billing day (45 s).** Billing → Dry run (8 subscriptions due today, nothing saved) → Run now → 8 invoices.
   Run now again → 0 created (never billed twice).
5. **Invoice and payment (45 s).** Open a new invoice: lines with discount and CGST/SGST (or IGST for other states).
   Confirm → Send (email file in `backend/sent_emails/`) → Print. Record a partial payment → still outstanding;
   record the rest → Paid.
6. **Finance lead (45 s).** Dashboard: active subscriptions, MRR, billed vs collected chart, overdue table,
   renewals and 30/60/90-day forecast, at-risk customers. Change the date range.
7. **Customer portal (30 s).** Log in as `customer@brightloop.test`: only Acme's subscriptions and invoices; pause
   or renew where the plan allows; print an invoice.

Recovery: `python scripts/dev.py seed --reset` rebuilds the demo data in about 15 seconds.
