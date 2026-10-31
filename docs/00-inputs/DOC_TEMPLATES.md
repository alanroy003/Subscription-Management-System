# DOC TEMPLATES

Place at `docs/00-inputs/DOC_TEMPLATES.md`. Claude copies these templates when it creates documents. Keep every document short and concrete: real field names, real examples, no filler.

Status markers used everywhere: **Not started / In progress / Built / Approved / Parked**.

---

## 1. Folder map

```
docs/
  00-inputs/        problem PDF, DOC_TEMPLATES.md, Stage 0 answers
  01-planning/      requirements.md, domain-model.md, architecture.md, security-and-auth.md,
                    billing-design.md, api-and-data.md, ux-and-screens.md, delivery-plan.md,
                    backlog/issues.csv, backlog/issues.json
  02-phase-1/       steps/S01-foundation/{spec.md, report.md} ... S11-hardening-release/
                    PHASE_1_SUMMARY.md
  03-phase-2/       steps/P2-01-payment-gateway/{spec.md, report.md} ...
  adr/              0001-title.md ...
  api/              public-api-guide.md, examples/
  runbooks/         setup.md, billing-run.md, recovery.md, demo.md
  PROJECT_STATUS.md  APPROVAL_LOG.md  TIME_LOG.md  CHANGELOG.md  HANDOFF.md  BACKLOG_PARKED.md
```

---

## 2. Requirement row (`01-planning/requirements.md`)

| ID | Source (scene and sentence) | Requirement | Priority | Step | Test | Issue | Status |
|---|---|---|---|---|---|---|---|
| FR-AUTH-003 | Scene 1: "password must be more than eight characters..." | Server-side policy: length 9 or more, one upper, one lower, one special | Must | S2 | `test_password_policy` | #12 | Not started |

ID prefixes: `FR-AUTH`, `FR-CAT` (catalog), `FR-QUO`, `FR-SUB`, `FR-INV`, `FR-DIS`, `FR-TAX`, `FR-PAY`, `FR-REP`, `FR-API`, `NFR-PERF`, `NFR-SEC`, `NFR-OPS`.
Rule: zero orphans. Every requirement has a step and a test. Every step's tests cite requirement IDs.

A section at the bottom lists **Assumptions** (each with the answer or default used and the date).

---

## 3. Step spec (`02-phase-1/steps/Sxx-name/spec.md`), written at kickoff

```markdown
# S6 Billing engine: spec
Status: In progress | Branch: step/S06-billing-engine | Estimate: 10-13 h | Tag on approval: v0.6.0

## Goal
One sentence.

## Requirements covered
FR-INV-001, FR-INV-002, NFR-PERF-001 ...

## Sub-tasks (each ends in a commit)
1. [ ] Due-subscription selection query (with tests)
2. [ ] Idempotent invoice generation (unique subscription + period)
3. ...

## Acceptance checks (testable)
- [ ] Re-running a billing run creates no duplicate invoices
- [ ] One failing subscription does not block the others
- [ ] Golden example passes

## Design notes
Links to ADRs, files to touch, extension points used.

## Risks
Risk, mitigation.

## Out of scope (parked)
Items moved to BACKLOG_PARKED.md.
```

---

## 4. Step report (`.../report.md`), max 25 lines, also posted in chat

```markdown
# S6 Billing engine: report
Date: YYYY-MM-DD | Branch: step/S06-billing-engine | PR: #NN | Commits: N (last abc1234)

## Built
- Short bullets with paths.

## Acceptance
| Check | Result |
|---|---|
| Re-run creates no duplicates | Pass |

## Tests and CI
Unit N, integration N, regression golden: pass. CI: green. Secret scan: clean.

## Time
Estimate 10-13 h | Actual 11.5 h | Phase 1 running total 41 h of 78-103 h

## Skills applied
codebase-design, supabase-postgres-best-practices, billing-tests

## Decisions and trade-offs
Short list, with ADR links.

## Risks and parked
Short list.

## Demo in 2 minutes
1. Run `python scripts/dev.py seed`.
2. Open Billing > Dry run, then Run now.
3. Re-run: show "0 created, N skipped".

## Question for you
The exact decision needed, or "Ready for APPROVED S6".
```

---

## 5. ADR (`adr/NNNN-title.md`)

```markdown
# ADR NNNN: Title
Status: Proposed | Accepted | Superseded by NNNN | Date: YYYY-MM-DD

## Context
The problem and constraints (hackathon time, free tooling, Windows).

## Options
1. Option A: pros, cons
2. Option B: pros, cons

## Decision
What we chose and why, in 2 to 4 sentences.

## Consequences
What gets easier, what gets harder, how to reverse it.

## Links
Requirements, steps, issues.
```

Required ADRs: auth approach, JWT verification method, schema and migration ownership, pooler mode, scheduler, money and rounding, PDF generation, API key design, UI direction.

---

## 6. Log formats (append-only)

**`APPROVAL_LOG.md`**
| Date | Gate or step | Status | Tag or commit | Approved by | Notes |
|---|---|---|---|---|---|
| 2026-11-02 | S4 | Approved | v0.4.0 | owner | GST presets included |

**`TIME_LOG.md`**
| Step | Estimate (h) | Actual (h) | Variance | Running total | Notes |
|---|---|---|---|---|---|
| S4 | 7-9 | 8.5 | in range | 28.5 | |

**`BACKLOG_PARKED.md`**
| Date | Idea | Reason parked | Suggested phase |
|---|---|---|---|

**`CHANGELOG.md`**: Keep a Changelog style, one entry per tag (Added / Changed / Fixed).

---

## 7. `PROJECT_STATUS.md`

```markdown
# Project status
Updated: YYYY-MM-DD | Phase: 1 | Cut line: B | Hours used: 41 of 78-103

## Steps
| Step | Name | Status | Tag | Est h | Actual h |
|---|---|---|---|---|---|
| S1 | Foundation | Approved | v0.1.0 | 5-6 | 6 |
| S6 | Billing engine | In progress | | 10-13 | |

## Scenes coverage (from the PDF)
| Scene | Status |
|---|---|
| 1 Sign-up and access | Approved |

## Now / Next / Blocked
Now: ... Next: ... Blocked: ...

## Top risks
...
```

---

## 8. `HANDOFF.md` (overwrite each time, max 80 lines)

```markdown
# Handoff
Timestamp | Branch | Last commit | git status summary

## Where we are
Phase, step, exact status.

## Approvals
Approved steps and tags (details in APPROVAL_LOG.md). Anything built but not approved, with the reason.

## Done this session
Bullets with paths.

## Unfinished
Exact file and the exact point reached.

## NEXT ACTION
One precise instruction.

## Decisions already made (do not re-ask)
Short list with ADR links.

## Open questions for the owner
List.

## Commands
How to run, test, lint, seed. Known failures.

## Read first
Ordered list, maximum 8 files. Skills to re-read.

## Reminders
Secrets in .env only; Windows-safe scripts; scope guard; approval phrase `APPROVED Sx`.
```

---

## 9. Pull request template (`.github/pull_request_template.md`)

```markdown
## Step
S__ : name | Closes #__ | Requirements: FR-__

## What changed
- 

## Acceptance checks
- [ ] Tests pass (unit, integration, regression)
- [ ] Lint and type checks pass
- [ ] Secret scan clean
- [ ] Docs updated (spec, report, status, changelog)
- [ ] Migrations reversible
- [ ] Negative authorization tests added where relevant

## Demo in 2 minutes
1. 

## Notes for review
Risks, parked items, dependencies added (with reason).
```

## 10. Issue templates (`.github/ISSUE_TEMPLATE/`)

`feature.yml` (fields: step, requirement IDs, description, acceptance criteria, estimate, dependencies), `bug.yml` (steps to reproduce, expected, actual, severity), `task.yml`, `adr.yml`.

Labels: `type:feature|bug|task|docs|adr`, `area:auth|catalog|billing|invoice|payment|portal|reporting|api|devops|ui`, `priority:must|should|could`, `phase:1|2`, `step:S1...S11`, `status:blocked`.

Milestones: `S1 Foundation` ... `S11 Hardening`, `Phase 2`.

## 11. Backlog CSV columns (`01-planning/backlog/issues.csv`)

`id, title, step, epic, requirement_ids, description, acceptance_criteria, estimate_h_low, estimate_h_high, priority, labels, milestone, depends_on, definition_of_done`

## 12. Commit examples

```
feat(auth): enforce password policy server-side [S2]
fix(billing): skip paused subscriptions in due query [S6]
test(billing): add golden worked example [S6]
docs(adr): record scheduler decision [S6]
chore(ci): add secret scan [S1]
```

## 13. Project skill skeleton (`.claude/skills/<name>/SKILL.md`)

```markdown
---
name: subscription-domain
description: Domain rules for the Brightloop subscription system: state machines, money and rounding, tax and discount rules, billing invariants. Use whenever touching subscriptions, invoices, payments, taxes or discounts.
---

# Subscription domain
## Invariants (never break)
## State machines (allowed transitions, who may act)
## Money and rounding
## Billing rules
## Glossary
```

Same layout for `step-gate` (the protocol, report format, approval phrases, handoff) and `billing-tests` (golden example, fixtures, property checks, how to run). Keep each under about 120 lines.

## 14. `PHASE_1_SUMMARY.md` (written at v1.0.0)

Scope delivered versus the PDF (scene by scene), actual versus estimated hours per step, what was parked, known limitations, demo script link, performance results, security checklist result, and the proposed order for Phase 2 by value per hour.
