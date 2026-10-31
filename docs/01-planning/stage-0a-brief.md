# Stage 0A: Understand and decide

Mode: PLAN. No application code. Status: awaiting owner answers (gate 0A).

## 1. Session and environment check

| Item | Result |
|---|---|
| Git, branch | OK. Planning work on `plan/stage-0`; `main` has only `README.md` |
| Node / Python / Docker | Node 24.21, Python 3.11.9, Docker 29.9.2 |
| `.env` | Present and gitignored. All 15 variables set (values not read or printed) |
| `DATABASE_URL` | Supabase **session pooler** (port 5432). Use this one |
| `SUPABASE_DB_URL` | Supabase **transaction pooler** (port 6543). Not suitable for Django (no server-side prepared statements / session state); leave unused |
| `.env` gaps | No `EMAIL_HOST`, `EMAIL_PORT`, `API_KEY_PEPPER`, `FEATURE_*` yet. Not blocking until S1/S2/S10 |
| `.env` leftovers | `VITE_ENABLE_THEME_LAB`, `VITE_ENABLE_SCHEMA_DESIGNER` (from the old template repo); will not be used |
| `gh` | Not authenticated: PRs and GitHub records need `gh auth login`, else manual steps |
| Housekeeping done | PDF moved `docs/inputs/` to `docs/00-inputs/`; `.gitattributes` (LF) added |
| Housekeeping noted | `.gitignore` last line `docs\00-inputs` is a stray paste. Harmless (matches nothing); remove in S1 |

### Skills
- Visible: `frontend-design`, `codebase-design`, `interaction-design`, `find-skills` (plus generic docs/pdf/xlsx skills).
- **Not visible:** `supabase`, `supabase-postgres-best-practices`, `design-taste-frontend`, `mcp-builder`, `grill-me`, `ask-matt`. Not found in `~/.claude/skills` or `.claude/skills`.
- Fallbacks: grill-me = one question at a time with a recommended answer (section 5); supabase skills = current Supabase docs checked at the point of use; design-taste = applied through `frontend-design` + tokens ADR.

## 2. The problem in our words

Brightloop runs a recurring-revenue business on spreadsheets and memory. Renewals slip, invoices are hand-typed and wrong, payments are matched by scrolling bank statements, and nobody knows the real recurring revenue. We build one system where:

1. **The catalog is defined once** (products, variants with price extras, plans with billing period and lifecycle options, taxes, discounts) by the admin.
2. **Sales becomes subscriptions** through quotation templates, with every subscription on a visible lifecycle (Draft, Quotation, Confirmed, Active, Closed).
3. **Billing runs itself**: invoices are produced from subscriptions on schedule, taxes and discounts applied by rule, never twice, never skipped.
4. **Cash is reconciled in the system**: payments recorded against invoices, paid versus outstanding versus overdue always visible.
5. **Each audience sees its slice**: admin everything, staff day-to-day, customers only their own subscriptions and invoices.
6. **Finance answers questions in seconds**, not days, at thousands of subscriptions.

The single test of success: run one realistic billing month end to end in the demo, from sign-up to the finance summary, with correct numbers.

## 3. Feasibility review

Overall: **feasible as Cut A in about 65 h, Cut B in about 95 h** (plus Stage 0, 4 to 6 h). Main risks, highest first:

| # | Risk | Why it matters | Mitigation (decided in 0C) |
|---|---|---|---|
| R1 | Billing correctness | It is the heart of the brief ("nothing billed twice or skipped") | Pure functions for price/tax/discount; unique `(subscription, period_start)`; golden test from S6 |
| R2 | **Supabase Auth email cannot reach local Mailpit** | Supabase sends reset mails from its cloud servers; free built-in mailer is rate-limited (a few per hour) | Django asks the Supabase Admin API to *generate* the recovery link and sends it itself through Mailpit (Q6) |
| R3 | Password policy bypass | Clients can call Supabase `signUp` directly and skip our rules | All sign-ups go through Django (Admin API); public sign-ups disabled in Supabase dashboard (Q6) |
| R4 | RLS is a no-op if Django connects as `postgres` | The `postgres` role bypasses RLS | Separate non-owner app role + `SET LOCAL app.customer_id` per request on portal tables only (Q7). Cost about 3 h |
| R5 | Session pooler connection limits | Free tier pooler has a small connection cap; Django + scheduler + tests | `CONN_MAX_AGE` small, scheduler single process, tests on local Postgres container |
| R6 | 2-second pages at 10k subs / 100k invoices | Dashboards over raw invoices get slow | Indexes on filter/join columns, pagination, monthly summary table refreshed by billing run |
| R7 | WeasyPrint on native Windows | Needs GTK/Pango, painful outside Docker | Run only inside the API container |
| R8 | Ambiguities in the PDF (plan price vs product price, renewal semantics) | Wrong guess = rework in S5/S6 | Questions Q3 to Q5 below |
| R9 | Owner review time | Estimates include your review; 15 gates in total | Two-minute demo recipe per step; batch questions |

Reuse: `START_HERE.md` mentions an earlier repo. I do not have its path. If you share it, I will name any file worth copying (likely only CI and Docker snippets); otherwise we start clean.

## 4. Cut line proposal (pending your hours)

| Cut | Hours | Keeps | Drops |
|---|---|---|---|
| A | 60 to 70 | S1 to S8 full; S9 lite (KPIs, overdue, MRR); S10 lite (keys + docs); S11 demo seed only | Revenue forecast, at-risk list, rate limits and idempotency header, 10k load test, extra charts, stretch |
| **B** | 80 to 105 | All Phase 1 core + Wow Pack | Stretch X1 to X3 |
| C | 100 to 128 | B + AI assistant, demo gateway, signed webhooks | Nothing in Phase 1 |

Rule I will apply: available hours x 0.85 (buffer) must cover the cut's upper bound. Example: 100 h available supports Cut A comfortably and Cut B only at the low end; 120 h supports Cut B.

## 5. Interview (grill-me fallback), in priority order

Each question has my recommended answer. "Accept all" is fine; edit any line.

**Q1 (blocking).** Available hours, team size, deadline, demo date, preferred cut. *Recommended:* tell me the numbers; I will propose the cut by the rule above.

**Q2. Defaults from `START_HERE.md`** (Paused status, invoice statuses incl. Cancelled, partial payments, INR, tax-exclusive per-line half-up rounding, GST presets, MRR normalisation, no discount stacking, no proration, Net terms, bill in advance on activation, daily run 02:00 IST with catch-up, portal pause/close/renew, Mailpit, JWT verification). *Recommended:* accept all.

**Q3. Plan price versus product price.** The PDF gives both a product sales price and a plan price. *Recommended:* the plan is the recurrence and has a per-period price for its base product; extra lines (add-ons) use the variant price (sales price + attribute extras). Line unit price is copied (snapshot) onto the subscription line and staff may edit it before confirmation.

**Q4. Confirmed versus Active, and expiry.** *Recommended:* Confirmed becomes Active automatically on the start date (immediately if the start date is today or earlier). At the expiry date: plans with auto-close go to Closed; renewable plans can be renewed (same subscription number, expiry extended by one term, logged in the timeline); otherwise they stay Active until closed by staff.

**Q5. Customer model.** *Recommended:* a Customer record (company or person, billing address, GST state, GSTIN optional) with one portal login in Phase 1. Staff can create customers without a login. Self-signed-up users become a Customer with a login. Customer state decides CGST+SGST versus IGST against the company's home state (setting).

**Q6. Sign-up and reset path.** *Recommended:* sign-up and reset requests go through Django, which enforces the password policy and calls the Supabase Admin API; Django emails the reset link via Mailpit. You disable "Allow new users to sign up" in the Supabase dashboard in S2. Email confirmation off in DEV.

**Q7. RLS scope.** *Recommended:* RLS as defense in depth on customer-scoped tables (subscriptions, invoices, payments, customers) using a non-owner app role; Django object-level permissions remain the primary control. Cut A fallback: Django-only with negative tests, RLS parked.

**Q8. Staff permissions.** *Recommended:* staff manage customers, quotations, subscriptions, invoices, payments and run billing; read-only on products, plans, taxes, discounts; no access to users, API keys, settings. Admin can do everything.

**Q9. Who creates subscriptions.** *Recommended:* staff create quotations and subscriptions; customers can accept a quotation in the portal (cheap, good demo). Self-checkout from a public pricing page is parked.

**Q10. Numbering.** *Recommended:* `SUB-2026-00001`, `INV-2026-00001`, `QT-2026-00001`, gap-free per year via a locked sequence table.

**Q11. Demo target.** *Recommended:* local Docker Compose on your laptop against Supabase DEV. Hosted deployment parked.

**Q12. Old repo.** *Recommended:* skip reuse unless you give me the path.

## 6. What happens after 0A

On `APPROVED 0A` with your answers saved to `docs/00-inputs/stage-0a-answers.md`, I start 0B: `requirements.md` (every PDF sentence to requirement ID, step and test) and `domain-model.md` (ERD, five state machines, money rules, worked example).
