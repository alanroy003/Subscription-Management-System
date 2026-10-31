# CLAUDE.md

Standing instructions for every session in this repo. Keep this file short; details live in `docs/`.

## Project
Brightloop Subscription Management System: products, plans, quotations, subscriptions, automatic invoicing, discounts, taxes, payments, customer portal, finance reporting, and a public API. Hackathon build with limited time. The problem statement is `docs/00-inputs/Subscription_Management_System.pdf` and it is the source of truth. The core objective is to solve that problem; everything else is an add-on.

## Stack
React + TypeScript + Vite · Django + Django REST Framework · Supabase (PostgreSQL, Auth) · Docker Compose · GitHub Actions. Free and local tools only (Mailpit, WeasyPrint, drf-spectacular, Recharts).

## Session start (always)
1. If `docs/HANDOFF.md` exists, read it first and continue from its NEXT ACTION.
2. Read `docs/APPROVAL_LOG.md` and `docs/PROJECT_STATUS.md`. Anything marked **Approved** is final: never redo or reopen it.
3. Read the project skills in `.claude/skills/` (`subscription-domain`, `step-gate`, `billing-tests`) once they exist.
4. State where we are in 3 lines, then continue. Do not re-ask decisions recorded in `docs/01-planning/` or `docs/adr/`.

## Environment
- Native Windows + PowerShell. Project scripts are Python (or Node), never bash-only. Use LF line endings.
- Commands: `python scripts/dev.py <doctor|up|down|seed|test|lint|migrate>`.
- Secrets live only in gitignored `.env` files. Never print, log or commit them, and never ask me to paste them. If one leaks, tell me to rotate it.
- Database: Supabase **Session pooler** connection.

## Scope guard
- Build only the current step. Park everything else in `docs/BACKLOG_PARKED.md`.
- No new dependency or service without a one-line justification in the step report.
- Do not start Phase 2 or any stretch item (AI, demo gateway, webhooks) without my approval.
- If a step passes 130% of its estimate, stop and tell me.

## Git and approval protocol
- `main` is always runnable. One branch per step: `step/S06-billing-engine`.
- Conventional Commits with the step tag: `feat(billing): add idempotent invoice generation [S6]`.
- Commit and push after every sub-task whose tests pass.
- At step end: run tests, lint, regression suite and secret scan; update docs; open a PR; post the Step Report; **stop**.
- Merge, tag and start the next step **only** after my exact phrase `APPROVED Sx`.
- Never force-push `main`. Never run destructive commands (`git reset --hard`, `git clean -fd`, dropping data) without my explicit OK. Migrations must be reversible.

## Non-negotiable engineering rules
- Money uses `Decimal`, never floats. Confirmed invoices are immutable. Tax and discount snapshots are stored on the invoice.
- Billing is idempotent: unique subscription and billing period, transactional, safe to re-run. Nothing billed twice, nothing skipped.
- Every authorization rule has a negative test (a customer cannot see another customer's data; only the admin can create staff).
- Every page responds in under 2 seconds at the seeded scale (10,000 subscriptions, 100,000 invoices).
- Keep the golden billing regression test green from S6 onward.
- Phase 2 features: feature flag, additive migrations only, Phase 1 regression suite stays green.

## Docs to keep current
`docs/PROJECT_STATUS.md`, `docs/APPROVAL_LOG.md`, `docs/TIME_LOG.md`, `docs/CHANGELOG.md`, step `spec.md` and `report.md`, ADRs for architectural decisions. Templates: `docs/00-inputs/DOC_TEMPLATES.md`.

## Context
If context passes about 70%, or at the end of a step, write `docs/HANDOFF.md` (maximum 80 lines), commit it, and print a ready-to-paste resume prompt.
