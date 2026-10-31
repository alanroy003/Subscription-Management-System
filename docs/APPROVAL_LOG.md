# Approval log (append-only)

| Date (IST) | Gate | Decision | Words |
|---|---|---|---|
| 2026-10-31 10:07 | Stage 0A to 0D and step gates S1 to S11 | Waived; Claude decides scope, stack trade-offs and order | "Okay the rest of the things you can decide ... I have given you that permission ... because of the time constraint I want an optimised result" |
| 2026-10-31 10:07 | Constraints | Solo, deadline 16:30 IST today | "I am a solo participant I have time till 4:30 PM" |
| 2026-10-31 10:58 | Git protocol | Manual commits: Claude prints COMMIT CHECKPOINTs; runs git commit/push only on `COMMIT IT` (CLAUDE.md, section "Git and approval protocol") | Owner pasted rule "8a. GITIGNORE AND MANUAL COMMIT CHECKPOINTS" and asked to "update the permission for the commit" |
| 2026-10-31 10:58 | Roadmap | `docs/01-planning/ROADMAP.md` written as PLAN only; steps start on `GO <step>` | "just plan it and after that we can execute" |
| 2026-10-31 | Roadmap decisions D1 to D5 | **Approved**: all recommended defaults (vendor-side platform, single company first, keep Django auth, Razorpay test mode, move Supabase to ap-south-1 when convenient) | "I will go with the recommended defaults ... let's go with what you have recommended" |
| 2026-10-31 | Working mode | Continuous step-by-step build (steps 1 to 37, then stretch) until the owner says `STOP AND SUBMIT`; then run the wrap-up procedure in ROADMAP.md section 6 | "if I want to stop it at any moment I will give you that instruction ... make it as ready and we can submit the hackathon" |
| 2026-10-31 | dev-tooling | **Approved** for merge to main (owner runs the merge); next: database integrity | "APPROVED, GO 3" |
| 2026-10-31 | db-integrity | **Approved** for merge to main (owner runs the merge); next: audit log, plus Swagger as backend documentation | "APPROVED, GO 4 ... Also in this step add the swagger as a back end documentation" |
| 2026-10-31 | Feature selection | **Approved**: build only 5, 6, 19, 20, 23, 24, 25, S1, S3 in that order; rest parked. gitleaks fix committed (46ca282) | "This is what I wish to implement in the next upcoming following phases ... lets move to the Server-side invoice PDF" |
