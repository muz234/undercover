# Status

Pilot in progress. Phase 1 of `docs/PLAN.md` is done.

- `backend/`: FastAPI and SQLite (`undercover.db` at the repo root, seeded from `data/` on first use; delete the file to reset). Read endpoints for claims, policies, customers, plans, handlers, company settings, policy wording and the agent's instructions. Write endpoints: decision, payment, sign-off and agent step events. A payout over $1,000 cannot be paid until a handler signs off, and signing off pays it.
- `agent/`: still the hello-world entry point `run(claim_id, thread_id)`.
- `dashboard/`: still the one page that shows whether the backend is up.
- `e2e/`: one test of that page.

Run: `npm run dev`. Check: `npm run check`.
