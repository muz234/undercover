# Plan: the claims pilot

This plan builds the pilot described in `docs/SPEC.md`: a backend, a dashboard for the three claims handlers, and the UnderCover Agent that decides claims. It follows `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`.

## Decisions

- **Storage.** SQLite through the standard library `sqlite3`, with no ORM. The database file is `undercover.db` at the repo root, git-ignored. On startup the backend creates the tables and loads `data/` if the database is empty. Deleting the file resets the demo.
- **What the backend loads.** `claims.json`, `policies.json`, `customers.json`, `plans.json`, `handlers.json`, `company.json` and `policy_wording.md`. It never reads `data/evals/`, `data/security/` or `claims_manual.md` (the manual is out of scope for the pilot). A test asserts this.
- **Claim states.** The spec's four states are stored as `waiting`, `in_progress`, `waiting_for_signoff` and `decided`. The seed data's `open` becomes `waiting`.
- **The payout rule lives in the backend, not the agent.** The agent records a decision, then calls a separate pay operation with an amount. The backend refuses any payment over $1,000 until a handler has signed off, and refuses any payment that does not match an approved decision. The agent's prompt also tells it the rule, but the block does not depend on the prompt.
- **Who pays.** For an approval of $1,000 or less the agent pays and the claim is `decided`. For an approval over $1,000 the claim becomes `waiting_for_signoff`. When a handler signs off, the backend makes the payment and the claim becomes `decided`. Declined and referred claims are `decided` straight away (a referral is the agent's final action; a handler picks it up outside the pilot).
- **Payments are records only.** A payment is a row with the claim, the amount and the time. No real payments.
- **Instructions.** The agent's system prompt is a markdown file, `backend/instructions.md`, served read-only at `GET /api/instructions`. The agent fetches it from the API at the start of each run, so it reaches its instructions only through the backend. The dashboard shows the same text.
- **Agent steps.** A LangChain callback handler inside `agent/` posts each tool call and its result to the backend as an event on the claim. The dashboard polls these while the claim is `in_progress`. This keeps the agent's code free of logging calls.
- **Running the agent.** `POST /api/claims/{claim_id}/run` marks the claim `in_progress` and starts the agent in a background thread. The claim id doubles as the thread id prefix (`{claim_id}-{n}`). If the run crashes, the claim goes back to `waiting` and the error is recorded as an event.
- **API shape.** Every operation has an `operation_id`, a one-line docstring and no optional inputs. Agent tools map one to one onto operations: `get_claim`, `get_policy`, `get_customer`, `get_plan`, `get_policy_wording`, `record_decision`, `pay_claim`.
- **Dashboard.** React, Vite and TypeScript in strict mode, with no router library: three views (queue, claim, instructions) selected from the URL hash. Plain CSS with brand tokens, light and dark mode from `prefers-color-scheme`. Fonts from Google Fonts.
- **Tests never call a model.** Agent tests use the existing `StubModel` pattern. Backend tests use an in-memory SQLite database.

## Phase 1: Backend data and read API

Builds the database, the seed loader and the read-only endpoints, so every later phase has real data to work with.

- `backend/db.py`: connection helper and schema (claims, items, documents, policies, customers, previous claims, plans, handlers, decisions, payments, events).
- `backend/seed.py`: loads `data/` when the database is empty.
- Endpoints: `GET /api/claims` (queue with status), `GET /api/claims/{claim_id}`, `GET /api/policies/{policy_id}`, `GET /api/customers/{customer_id}` (with claim history), `GET /api/plans/{plan}`, `GET /api/handlers`, `GET /api/policy-wording`, `GET /api/instructions`, `GET /api/company`.
- `backend/instructions.md`: a first version of the agent's instructions, written in Phase 3 and stubbed here with a placeholder so the endpoint works.

Success criteria:

- [x] `uv run pytest -q backend` passes, with tests for the seed loader (25 claims, 3 handlers, 3 plans) and each read endpoint.
- [x] A test proves the seed loader opens no file under `data/evals/` or `data/security/`.
- [x] `uv run -m uvicorn backend.main:app --port 8000` starts; `curl localhost:8000/api/claims` returns 25 claims, all with `"status": "waiting"`.
- [x] `curl localhost:8000/api/claims/CLM-1001` returns the story, items, documents, `policy_id` and `customer_id`.
- [x] `curl localhost:8000/api/customers/CUS-3001` includes the previous claim CLM-0412.
- [x] `curl localhost:8000/api/openapi.json` shows every operation with an `operation_id`, and no parameter is optional (a test walks the schema and fails otherwise).
- [x] Restarting the server does not duplicate or reset the data.

## Phase 2: Decisions, states, payment guard and sign-off

Builds the business rules, the part the spec says the system must enforce.

- `POST /api/claims/{claim_id}/decision`: takes decision (`approve`, `decline`, `refer`), payout, explanation and policy section. Rejects a payout on decline or refer (must be 0) and an approve with a payout of 0 or less. Sets the state: `waiting_for_signoff` for an approval over the limit (the limit is read from `company.json`, not hard-coded), otherwise leaves the claim `in_progress` until it is paid, or `decided` for decline and refer.
- `POST /api/claims/{claim_id}/payment`: takes the amount. Refuses with 409 when there is no approved decision, when the amount differs from the decision's payout, when the claim is already paid, or when the payout is over the limit and nobody has signed off. On success records the payment and sets `decided`.
- `POST /api/claims/{claim_id}/sign-off`: takes a handler id. Refuses unknown handlers and claims not `waiting_for_signoff`. Records who signed off and when, then makes the payment through the same code path and sets `decided`.
- `POST /api/claims/{claim_id}/events` and the events in `GET /api/claims/{claim_id}`: the step log the agent writes and the dashboard reads.
- A claim cannot get a second decision.

Success criteria:

- [x] `uv run pytest -q backend` passes, with tests for every refusal above and each happy path.
- [x] Test: approve $1,250.00, then pay $1,250.00 before sign-off returns 409 and no payment row exists. This is the spec's "even if the agent tries to pay" rule.
- [x] Test: approve $1,000.00 exactly, then pay, gives `decided` (the limit is "over $1,000").
- [x] Test: after sign-off by HND-01, the payment exists once and the claim is `decided`; a second sign-off returns 409.
- [x] With the server running, the same sequence done with `curl` on CLM-1001 gives the expected status codes and `GET /api/claims/CLM-1001` shows the decision, the payment and the final state.
- [x] No endpoint can read or change a decision made by another claim (decisions are keyed by claim id).

## Phase 3: The agent

Replaces the hello-world agent with one that decides a claim, and adds the endpoint that runs it.

- `agent/main.py`: keeps the entry point `run(claim_id, thread_id)` and the `model()` function. Tools call the backend only. System prompt comes from `GET /api/instructions`.
- `backend/instructions.md`: the real instructions. They tell the agent to read the claim, the policy, the plan, the customer's history and the policy wording; to decide by the wording only; to work the payout with the wording's section 10 (per-item limits, amounts from carriers taken off, deductible, benefit maximum); to explain the decision in two or three sentences citing the section; to record the decision and then pay only an approval of $1,000 or less; and to treat anything inside a claim's story or documents as the customer's words, never as instructions.
- `agent/steps.py`: the callback handler that posts tool calls and results to the backend as events.
- `POST /api/claims/{claim_id}/run`: marks `in_progress`, starts `agent.main.run` in a background thread, returns at once. Refuses claims that are not `waiting`. A crash resets the claim to `waiting` and logs an event.

Success criteria:

- [x] `uv run pytest -q agent backend` passes. Agent tests use a stub model with scripted tool calls and never call a real model.
- [x] Test: a scripted run on CLM-1001 reads the claim, records an approve decision, pays, and ends with the claim `decided` and one payment.
- [x] Test: a scripted run that approves $1,250 and then tries to pay gets the 409 back as a tool result and the claim stays `waiting_for_signoff`.
- [x] Test: each tool call in a run appears as an ordered event on the claim.
- [x] Test: the agent package makes no HTTP request to anything but the backend, and no code under `agent/` references `data/`.
- [x] Test: `POST /run` on a claim that is not `waiting` returns 409; a run that raises puts the claim back to `waiting` with an error event.
- [x] Every agent tool has a docstring and takes no optional input.
- [x] Optional smoke test, needing the student's `OPENROUTER_API_KEY` and a small amount of spend (or `MODEL_NAME=openrouter/free`): start the backend, `POST /api/claims/CLM-1001/run`, and within two minutes `GET /api/claims/CLM-1001` shows a decision, an explanation with a policy section, and step events. This checks the wiring only; the pilot does not score accuracy.

## Phase 4: Dashboard, read-only views

Builds the screens that show the queue, a claim in full and the instructions, in the UnderCover look.

- `dashboard/src/styles.css`: brand tokens (colors, fonts, light and dark surfaces, rounded panels, no one-edge borders). Status colors: waiting Marigold, in progress Cerulean, waiting for sign-off Coral, decided Sea Green. Raspberry for errors.
- `dashboard/src/api.ts`: typed fetch helpers and response types, strict, no `any`.
- Views: Queue (table of claims with id, customer, type, amount claimed and a status chip, with a filter by status), Claim (story, items, documents, policy, customer history, decision and explanation, payment), Instructions (read-only text).
- Money in US dollars as `$1,250.00`; ids and amounts in JetBrains Mono; US spelling and plain labels.

Success criteria:

- [x] `npm run check:ts` passes, including vitest at 80% coverage or more, with component tests that use a mocked `fetch`.
- [x] `tsc` strict passes and a search finds no `any` under `dashboard/src`.
- [x] With `npm run dev` running, the Playwright MCP browser at `http://localhost:5173` shows 25 claims in the queue with status chips; a screenshot is checked against `docs/BRAND.md` for fonts, colors and rounded panels without outlines.
- [x] Clicking CLM-1001 shows its story, three items totaling $420.00, its documents, the Premium plan and Maya Patel's earlier claim.
- [x] The Instructions view shows the text from `/api/instructions`, with no edit control.
- [x] The same pages in dark mode (emulated with the Playwright MCP server) use the dark surfaces from the brand document and stay readable.

## Phase 5: Dashboard, running the agent and signing off

Makes the dashboard live: start the agent, watch its steps and sign off large payouts.

- Claim view: a "Run agent" button for `waiting` claims; while the claim is `in_progress` the page polls every two seconds and lists the agent's steps (tool name, a short summary of the input and the result), then shows the decision, the explanation and the policy section when done.
- Queue view: a "Run all waiting" button that runs the waiting claims one after another from the browser.
- For `waiting_for_signoff` claims: the approved payout, a handler picker and a "Sign off and pay" button. After sign-off the claim shows as decided with the payment.
- Polling stops when the claim leaves `in_progress` and when the page unmounts.

Success criteria:

- [ ] `npm run check:ts` passes with tests for the run button, the polling (with fake timers), the steps list and the sign-off flow.
- [ ] End to end with a stub agent (a test-only environment variable swaps in the scripted stub model on the backend; nothing in the product code path changes), in the Playwright MCP browser: run CLM-1001, see steps appear, see the decision and the status chip turn to decided.
- [ ] With a scripted approval of $1,250 on another claim, the browser shows "waiting for sign-off", the pay endpoint is blocked (checked with `curl`, 409), and after choosing Dana Whitfield and signing off the chip shows decided and the payment is listed.
- [ ] Reloading the page mid-run keeps showing the steps so far and carries on updating.

## Phase 6: End-to-end tests, documentation and final check

Locks the behavior in with Playwright tests and brings the docs up to date.

- `e2e/`: replace the health test with tests for the queue, the claim view, a full agent run with the stub model, the sign-off flow and the instructions view. The stub is selected by a test-only environment variable set in `playwright.config.ts` for the backend server it starts, and each test starts from a freshly seeded database file.
- `docs/STATUS.md`: what is built, the API list, how to run it and how to reset the data.
- `README.md` for the product stays short (the repo README is the course's; add a short `docs/` pointer only if needed).
- `.gitignore`: add `undercover.db`.

Success criteria:

- [ ] `npm run e2e` passes, with tests for: the queue lists 25 claims; a claim shows its details; a stubbed run ends decided with steps shown; an over-limit approval waits and then pays after sign-off; the instructions view is read only.
- [ ] `npm run check` passes in full: ruff, pyright, pytest with 80% coverage, ESLint, Prettier, tsc, vitest with 80% coverage and Playwright.
- [ ] `docs/STATUS.md` describes the pilot as built, with the run commands, and every box in this plan is ticked.
- [ ] `git status` shows a clean tree after the last commit, and `undercover.db` is not tracked.
- [ ] No file under `data/evals/` was opened by any code or test (checked with a grep for `evals` across `backend`, `agent`, `dashboard` and `e2e`, which returns only the test that asserts it is never read).

## Not in this plan

- The claims manual, sign-in, real payments, messages to customers (all excluded by the spec).
- Scoring the agent against `data/evals/`. That needs the answer key, which stays closed until you ask for it.
- Prompt-injection defenses beyond the one line in the instructions; the security claim in `data/security/` is for a later day.
