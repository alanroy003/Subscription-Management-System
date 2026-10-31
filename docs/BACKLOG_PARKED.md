# Parked backlog

| Item | Reason parked |
|---|---|
| Supabase Auth + JWT verification | Time box; Django auth covers every auth requirement in the PDF (ADR 0001) |
| Per-customer RLS policies | Django connects as owner; isolation enforced in querysets with negative tests; RLS-on/no-policy blocks the Data API |
| Docker Compose + Mailpit container | Docker daemon not running; native run is faster; email falls back to files |
| WeasyPrint server-side PDF | Browser print gives the same document without GTK on Windows |
| Public API keys, idempotency header, rate limits (beyond auth throttling) | Not in the PDF; Wow Pack item, time box |
| Signed webhooks, AI assistant, demo payment gateway | Stretch |
| Domain event outbox | Subscription timeline (`SubscriptionEvent`) is the audit trail for now |
| Credit notes, refunds, proration, upgrades/downgrades | Phase 2 |
| Self-checkout from a public pricing page | Not in the PDF; customers sign up and staff quote |
| GitHub labels, milestones, project board | `gh` not authenticated |
