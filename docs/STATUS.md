# Status

Pilot in progress. Phases 1 to 4 of `docs/PLAN.md` are done.

- `backend/`: FastAPI and SQLite (`undercover.db` at the repo root, seeded from `data/` on first use; delete the file to reset). Read endpoints for claims, policies, customers, plans, handlers, company settings, policy wording and the agent's instructions. Write endpoints: decision, payment, sign-off and agent step events. A payout over $1,000 cannot be paid until a handler signs off, and signing off pays it.
- `agent/`: `run(claim_id, thread_id)` decides one claim. Its tools (`get_claim`, `get_policy`, `get_plan`, `get_customer`, `get_policy_wording`, `record_decision`, `pay_claim`) call the backend API only, and it loads its instructions from `GET /api/instructions` (`backend/instructions.md`). Each tool call is posted to the claim as a step. `POST /api/claims/{id}/run` starts it in the background.
- `dashboard/`: React, Vite and TypeScript. Read-only views: the claims queue with status chips and a status filter, a claim in full, and the agent's instructions. Brand styles in `src/styles.css`, light and dark.
- `e2e/`: one test that the queue lists the claims.

Run: `npm run dev`. Check: `npm run check`.
