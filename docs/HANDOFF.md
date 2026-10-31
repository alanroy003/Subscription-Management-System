# Handoff

## Where we are
v1.1.0 hackathon submission (2026-10-31). Branch `submission` holds the final state (built on `free-trial`).
Every PDF scene plus invoice PDFs, renewal reminders, free trials, database integrity, audit log, API docs and the
public API are built, tested (SQLite 69 + 7 skipped, Postgres 76) and demoed against Supabase.

## Approvals
All owner approvals are in `docs/APPROVAL_LOG.md`. Commits are made by the owner (CLAUDE.md).

## NEXT ACTION
Owner merges `submission` into `main` (pull request) and tags `v1.1.0-submission`. Optional after the hackathon:
fix the SQLite "adds up" check (`docs/BACKLOG_PARKED.md`), run Docker Compose, move Supabase to ap-south-1.

## Decisions already made (do not re-ask)
ADR 0001 (Django auth, session pooler, RLS on, browser print), ADR 0002 (database money rules, reconciliation),
ADR 0003 (xhtml2pdf for PDFs). Feature order chosen by the owner: see APPROVAL_LOG.

## Commands
`python scripts/dev.py setup | doctor | up | test [--pg] | lint | seed --reset | perf` ·
`python backend/manage.py run_billing | send_renewal_reminders | reconcile`

## Read first
`SUBMISSION.md`, `README.md`, `docs/runbooks/demo.md`, `backend/core/services.py`.
