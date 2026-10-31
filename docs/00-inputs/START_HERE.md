# START HERE

How to start the Brightloop Subscription Management System project with Claude Code, and exactly what to say at each point.

Files in this pack:

| File | Where it goes | Purpose |
|---|---|---|
| `MASTER_PROMPT.md` | Anywhere (you paste it into Claude Code) | The complete plan, phases, steps, git protocol, rules |
| `CLAUDE.md` | Repo root | Standing instructions Claude reads in every session |
| `DOC_TEMPLATES.md` | `docs/00-inputs/` | Templates for step specs, reports, ADRs, logs, handoff |
| `START_HERE.md` | `docs/00-inputs/` (optional) | This guide |
| The problem PDF | `docs/00-inputs/Subscription_Management_System.pdf` | The source of truth for requirements |

---

## 1. One-time setup (about 20 minutes)

**Recommended: a new repository.** The earlier generic foundation (UI template library, CRUD engine) is larger than a hackathon needs. Keep the old repo as a reference. Claude's reuse assessment in Stage 0A will name any specific file worth copying.

1. Create a new empty GitHub repo, for example `brightloop-subscriptions`, and clone it.
2. In PowerShell, inside the repo:
```powershell
New-Item -ItemType Directory -Force docs\00-inputs | Out-Null
```
3. Copy the files from the table above into place, and add the PDF.
4. Create `.gitignore` (ASCII encoding) with at least:
```gitignore
.env
.env.*
!.env.example
node_modules/
__pycache__/
*.pyc
.venv/
dist/
build/
.DS_Store
```
5. Create `.gitattributes` with `* text=auto eol=lf` and `*.ps1 text eol=crlf` (use `-Encoding ascii` if you create it with `Set-Content`).
6. Create your local `.env` (never committed). Use the **Session pooler** string from Supabase, and a **new** database password if the old one was ever shared:
```dotenv
# Supabase (DEV project)
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_REPLACE_ME
SUPABASE_SECRET_KEY=
DATABASE_URL=REPLACE_WITH_SESSION_POOLER_STRING

# Django
DJANGO_SETTINGS_MODULE=config.settings.dev
DJANGO_SECRET_KEY=REPLACE_WITH_GENERATED_VALUE
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173

# Local email (Mailpit)
EMAIL_HOST=mailpit
EMAIL_PORT=1025

# Public API
API_KEY_PEPPER=REPLACE_WITH_GENERATED_VALUE

# Feature flags (Phase 2 and stretch stay off)
FEATURE_AI_ASSISTANT=false
FEATURE_DEMO_GATEWAY=false
FEATURE_WEBHOOKS=false
ANTHROPIC_API_KEY=

# Frontend
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_REPLACE_ME
```
Generate secrets with: `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
7. Make sure Docker Desktop is running, then make the first commit:
```powershell
git add -A
git commit -m "chore: add problem statement, master prompt inputs and CLAUDE.md"
git push -u origin main
```
8. Make sure the GitHub CLI is signed in if you want Claude to open pull requests: `gh auth login`. Without it, Claude will give you manual steps.

---

## 2. What to say, in order

### Message 1: environment check (paste first)
```text
Read CLAUDE.md. Then, without starting any project work:
1. List every skill you can see in this session. I expect: supabase,
   supabase-postgres-best-practices, frontend-design, design-taste-frontend, mcp-builder,
   and possibly grill-me, codebase-design, interaction-design. Tell me which are missing.
2. Check that Git, Node, Python 3.11+, Docker and Docker Compose work, and that Docker is running.
3. Check that .env exists and that DATABASE_URL, SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY are set.
   Do NOT print their values.
4. Test the database connection with a throwaway script that prints only "connected" or
   the error type. Do not create tables.
5. Check whether gh is authenticated (gh auth status).
Report pass or fail per item and what you need from me. Do not start Stage 0.
```

### Message 2: the master prompt
When Message 1 is clean, paste the full `MASTER_PROMPT.md`. Claude begins Stage 0A.

### Message 3: your Stage 0A answers
Claude will ask questions. Answer with this form, editing the first block. Saying "accept all defaults" for the second block is fine, and you can change any line.

```text
STAGE 0A ANSWERS
Available time: ___ hours total. Team: ___ people. Deadline: ___. Demo date: ___.
Preferred cut line: A / B / C (or "you propose").

Defaults I accept unless I edit them below:
- Paused is a separate subscription status (Draft, Quotation, Confirmed, Active, Paused, Closed). Billing is skipped while paused.
- Invoice statuses: Draft, Confirmed, Paid, Cancelled. Credit notes and refunds are Phase 2.
- Partial and multiple payments are allowed. An invoice becomes Paid when allocated payments reach the total. Overpayment is rejected in the MVP.
- Single currency (INR), stored with a currency code. Prices are tax-exclusive. Tax is computed per line. Rounding is per line, half-up, 2 decimals. Invoice total is the sum of its lines.
- GST presets: CGST+SGST (intra-state) and IGST (inter-state), as admin-editable tax groups.
- Revenue shows three numbers with clear definitions: billed, collected, and MRR. MRR normalises yearly by 12, weekly by 52/12, daily by 365/12.
- Discounts apply before tax. No stacking: the single best eligible discount applies per line, plus at most one subscription-level discount. The usage limit is global, counted per invoice generated and released if that invoice is cancelled.
- Proration, upgrades, downgrades and mid-cycle quantity changes are Phase 2.
- Payment terms: Immediate, Net 15, Net 30, Net 45 (admin-editable). Due date is invoice date plus the term. Overdue means due date passed and not fully paid.
- First invoice is created when a subscription becomes Active (billing in advance). Later invoices are created on each period start.
- Billing run: daily at 02:00, time zone Asia/Kolkata, with catch-up for missed days.
- Portal: view own subscriptions and invoices, download PDF, pause, close and renew where the plan allows. Pay online is stretch.
- Email: Mailpit locally; SMTP settings come from env for any deployed environment.
- Auth: Supabase Auth with JWT verified by Django (decide JWKS or shared secret after checking the project's key type).

Changes to the defaults above:
(write any changes here, or "none")
```

### Message 4 onward: approvals and control
Use these exact phrases. They are what `CLAUDE.md` and the master prompt listen for.

| You want to | Say |
|---|---|
| Approve a planning gate | `APPROVED 0A` (or 0B, 0C, 0D) |
| Approve a step: merge, tag, start the next | `APPROVED S4` |
| Ask for changes before approving | `CHANGES S4: <numbered list>` |
| Let it begin a gated step (S2, S4, S6) | `GO S6` |
| Stop work and wait | `HOLD` |
| Park an idea without building it | `PARK: <idea>` |
| Check progress | `STATUS` (it prints step, hours used versus estimate, next action) |
| Re-estimate the plan | `RE-ESTIMATE` (it proposes a smaller cut if you are over 30%) |
| Cut scope | `CUT: <feature>` |
| Save state and prepare a new session | `HANDOFF` |
| Undo an approved step | `ROLLBACK to v0.5.0` (it explains the effect, then asks to confirm) |
| Start Phase 2 | `START PHASE 2` (it first proposes the order) |

### After a handoff: resume in a fresh session
```text
RESUME. Read CLAUDE.md, docs/HANDOFF.md, docs/APPROVAL_LOG.md and docs/PROJECT_STATUS.md.
Verify the branch, last commit and working tree match the handoff. Re-read the project skills.
Reply with 3 lines (where we are, NEXT ACTION, anything blocked), then continue.
Treat everything marked Approved as final.
```

---

## 3. What a good session looks like

1. **Stage 0 (4 to 6 h, four gates):** questions, plan, domain model, design, backlog. You approve each gate. Nothing is built.
2. **S1 to S11:** each step ends with commits on a branch, a green CI run, updated docs, and a short report with a 2-minute demo recipe. You test it, then say `APPROVED Sx`.
3. **At every approval:** Claude merges, tags (`v0.x.0`), and logs it in `APPROVAL_LOG.md` and `TIME_LOG.md`.
4. **S11:** `v1.0.0` and `release/1.x`. Phase 1 is complete and demo-ready.
5. **Phase 2:** each add-on on its own branch behind a flag, with the regression suite as the gate.

## 4. Things to watch

- **Review the report, not the diff:** each report lists acceptance checks and a 2-minute demo recipe. Run the demo, then approve.
- **Your time counts:** the hour estimates include your review time. If you skip review, you are borrowing from the next step.
- **Burn alert:** Claude stops at 130% of a step's estimate. Decide whether to cut scope instead of letting it run on.
- **Never paste secrets into chat.** If Claude needs a value, it should name the `.env` variable.
- **Context:** ask for a `HANDOFF` at the end of each step, or when Claude's context passes about 70%.
