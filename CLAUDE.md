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
- `main` is always runnable. One branch per feature with a plain name, no step numbers: `db-integrity`, `usage-alerts`.
- Commit messages are short and natural, written like a person would: `Add database checks for invoice totals`.
  No step tags, no `[Sx]`, no type prefixes, no mention of steps or tooling chatter; optional second line only if useful.
- **Manual commits (since 2026-10-31):** never run `git commit` or `git push` unless I say `COMMIT IT`.
  Print a **COMMIT CHECKPOINT** and wait when the tree has changes and any trigger is true: a sub-task is done and its
  tests pass; the last commit is > 30 min old (`git log -1 --format=%cI`) or > ~10 files / 300 lines changed; before a
  risky change (migration, dependency change, large refactor, merge); at every step end before the Step Report.
- COMMIT CHECKPOINT (max 12 lines): changed-files summary; checks (tests, ignored-file check, secret scan); then exactly:
  `git status` · `git add -A` · `git commit -m "<short natural summary>"` · `git push`.
- Before every checkpoint run `git status --porcelain` and `git check-ignore -v .env`; nothing sensitive or generated may
  be staged (no `.env*` except `.env.example`, keys, dumps, logs, build output, dependency folders). If it is: stop,
  `git rm --cached`, fix `.gitignore`, tell me. If a secret was ever committed, tell me to rotate it. No history rewrite
  without my approval. Update `.gitignore` in the same change whenever a new tool, folder or generated file appears.
- My replies: `COMMITTED` (record the hash, continue), `COMMIT IT` (run exactly those commands), `CHANGE MSG: <text>`,
  `LATER` (ask again at the next trigger, never later than the step end). Never move past a step end with uncommitted work.
- At step end: run tests, lint, regression suite and secret scan; update docs; print the checkpoint; post the Step Report; **stop**.
- Start a roadmap step only after my `GO <n>`. On `STOP AND SUBMIT`, follow ROADMAP.md section 6.
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
