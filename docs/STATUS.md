# Status

The claims pilot is built: every phase of `docs/PLAN.md` is done.

## What is built

- `backend/`: FastAPI and SQLite. The database is `undercover.db` at the repo root (git-ignored), seeded from `data/` on first use. Delete the file to reset. It never reads `data/evals/`, `data/security/` or the claims manual.
- `agent/`: `run(claim_id, thread_id)` decides one claim. Its tools (`get_claim`, `get_policy`, `get_plan`, `get_customer`, `get_policy_wording`, `record_decision`, `pay_claim`) call the backend API only, and it loads its instructions from `GET /api/instructions` (`backend/instructions.md`). Each tool call is posted to the claim as a step. Setting `UNDERCOVER_SCRIPTED_MODEL=1` swaps in a scripted model that approves the amount claimed, for end-to-end tests.
- `dashboard/`: React, Vite and TypeScript. The claims queue with status chips, a status filter and Run all waiting; a claim in full with Run agent, the agent's steps (polled every two seconds while it runs; the queue and the claim page refresh every 60 seconds otherwise), its decision, and a sign-off form; and the agent's instructions, read only. Brand styles in `src/styles.css`, light and dark.
- `e2e/`: Playwright tests of the queue, a claim, an agent run, the sign-off flow and the instructions. They run against a scripted model and a fresh temporary database.

## Rules the backend enforces

- A claim is `waiting`, `in_progress`, `waiting_for_signoff` or `decided`.
- A payout over $1,000 (`payout_approval_limit` in `data/company.json`) cannot be paid until a handler signs off. Signing off pays it.
- A claim gets one decision. A payment must match the approved payout, and a claim is paid once.

## API

`GET /api/claims`, `/api/claims/{id}`, `/api/policies/{id}`, `/api/customers/{id}`, `/api/plans/{plan}`, `/api/handlers`, `/api/company`, `/api/policy-wording`, `/api/instructions`. `POST /api/claims/{id}/decision`, `/payment`, `/sign-off`, `/events` and `/run`. The full list is at `/api/openapi.json`.

## Run

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173. Set `OPENROUTER_API_KEY` in `.env`, and optionally `MODEL_NAME` such as `openrouter/free`.
- `npm run check` runs every check. Stop `npm run dev` first: the end-to-end tests start their own backend on port 8000.

## Held-out score

`uv run scoring/score_held_out.py` runs the agent on the 25 held-out claims through a temporary backend on port 8100 and scores it against the answer key, which is read only after the runs. It takes about 12 minutes at OpenRouter's 20 requests per minute limit for new accounts. Result with `openai/gpt-6-luna`: 21/25 fully correct (routine 15/15, hard 5/5, manual 1/5) after adding a rule that a document missing something the wording asks it to show counts as missing. That rule was written after reading two held-out claims, so this score is no longer a clean test. The four misses are all manual-tagged and need the claims manual, which the pilot leaves out.
