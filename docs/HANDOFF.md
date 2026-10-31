# Handoff

## Where we are
Time-boxed MVP (owner: solo, deadline 2026-10-31 16:30 IST, all decisions delegated to Claude). Every PDF scene and the
Wow Pack public API are built, tested (25 backend tests) and checked in the browser against Supabase. `main` is pushed.

## Approvals
Stage 0 and step gates waived by the owner on 2026-10-31 10:07 (see `APPROVAL_LOG.md`).

## NEXT ACTION
Owner runs the demo (`docs/runbooks/demo.md`). Optional: start Docker Desktop and verify `docker compose up --build`.

## Decisions already made (do not re-ask)
ADR 0001: Django token auth (not Supabase Auth), session pooler + psycopg pool, RLS on/no policies, browser print for
PDF, file email backend unless `EMAIL_HOST`, SQLite tests, gap-free numbering, parallel billing per subscription.

## Open questions for the owner
1. Move the Supabase project to `ap-south-1` (Mumbai)? Billing writes would be ~5x faster from India.
2. Which stretch item next, if any: demo payment gateway, signed webhooks, AI assistant?

## Commands
`python scripts/dev.py up | test | perf | seed --reset | billing --dry-run` · `docker compose up --build`

## Read first
`README.md`, `docs/01-planning/mvp-plan.md`, `docs/adr/0001-time-boxed-mvp.md`, `backend/core/services.py`.

## Reminders
Demo logins are the seeded `@brightloop.test` users; password is `DEMO_PASSWORD` or the seed default. Never commit `.env`.
