"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from pydantic import BaseModel

from agent.main import run as run_agent
from backend import db

app = FastAPI(title="UnderCover", openapi_url="/api/openapi.json")


def get_db() -> Iterator[sqlite3.Connection]:
    """Open a database connection for one request."""
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(get_db)]


def record(conn: sqlite3.Connection, kind: str, record_id: str) -> dict[str, Any]:
    """Return one policy, customer, handler or plan, or raise 404."""
    row = conn.execute(
        "SELECT data FROM records WHERE kind = ? AND id = ?", (kind, record_id)
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"No {kind} {record_id}")
    return json.loads(row["data"])


def claim_row(conn: sqlite3.Connection, claim_id: str) -> dict[str, Any]:
    """Return a claim with its status, or raise 404."""
    row = conn.execute(
        "SELECT status, data FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"No claim {claim_id}")
    return {**json.loads(row["data"]), "status": row["status"]}


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(conn: Conn) -> list[dict[str, Any]]:
    """List the claims queue with each claim's status."""
    names = {
        row["id"]: json.loads(row["data"])["name"]
        for row in conn.execute("SELECT id, data FROM records WHERE kind = 'customer'")
    }
    queue = []
    for row in conn.execute("SELECT status, data FROM claims ORDER BY claim_id"):
        claim = json.loads(row["data"])
        queue.append(
            {
                "claim_id": claim["claim_id"],
                "customer_name": names[claim["customer_id"]],
                "claim_type": claim["claim_type"],
                "summary": claim["summary"],
                "submitted_on": claim["submitted_on"],
                "amount_claimed": claim["amount_claimed"],
                "status": row["status"],
            }
        )
    return queue


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, conn: Conn) -> dict[str, Any]:
    """Get a claim in full with its decision, sign-off, payment and steps."""
    claim = claim_row(conn, claim_id)
    decision = conn.execute(
        "SELECT * FROM decisions WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    signoff = conn.execute(
        "SELECT * FROM signoffs WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    payment = conn.execute(
        "SELECT * FROM payments WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    events = conn.execute(
        "SELECT id, tool, input, result, at FROM events WHERE claim_id = ? ORDER BY id",
        (claim_id,),
    ).fetchall()
    return {
        **claim,
        "decision": dict(decision) if decision else None,
        "signoff": dict(signoff) if signoff else None,
        "payment": dict(payment) if payment else None,
        "events": [dict(event) for event in events],
    }


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, conn: Conn) -> dict[str, Any]:
    """Get a policy with its plan, add-ons, trip and travelers."""
    return record(conn, "policy", policy_id)


@app.get("/api/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str, conn: Conn) -> dict[str, Any]:
    """Get a customer with their claim history."""
    return record(conn, "customer", customer_id)


@app.get("/api/plans/{plan}", operation_id="get_plan")
def get_plan(plan: str, conn: Conn) -> dict[str, Any]:
    """Get the limits, waiting periods and deductible of a plan."""
    return record(conn, "plan", plan)


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(conn: Conn) -> list[dict[str, Any]]:
    """List the claims handlers."""
    rows = conn.execute("SELECT data FROM records WHERE kind = 'handler' ORDER BY id")
    return [json.loads(row["data"]) for row in rows]


@app.get("/api/company", operation_id="get_company")
def get_company() -> dict[str, Any]:
    """Get the company settings, including the payout approval limit."""
    return db.company()


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> dict[str, str]:
    """Get the policy wording the agent decides claims by."""
    return {"text": db.policy_wording()}


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> dict[str, str]:
    """Get the agent's instructions."""
    return {"text": (Path(__file__).parent / "instructions.md").read_text("utf-8")}


class DecisionBody(BaseModel):
    """A decision on a claim."""

    decision: Literal["approve", "decline", "refer"]
    payout: float
    explanation: str
    policy_section: str


class PaymentBody(BaseModel):
    """A payment of a claim."""

    amount: float


class SignOffBody(BaseModel):
    """A handler's sign-off."""

    handler_id: str


class EventBody(BaseModel):
    """One step the agent took."""

    tool: str
    input: str
    result: str


def now() -> str:
    """Return the current time as text."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def set_status(conn: sqlite3.Connection, claim_id: str, status: str) -> None:
    """Set a claim's status."""
    conn.execute("UPDATE claims SET status = ? WHERE claim_id = ?", (status, claim_id))


@app.post("/api/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(claim_id: str, body: DecisionBody, conn: Conn) -> dict[str, Any]:
    """Record the decision on a claim."""
    claim = claim_row(conn, claim_id)
    if claim["status"] not in ("waiting", "in_progress"):
        raise HTTPException(409, f"Claim is {claim['status']}")
    if conn.execute(
        "SELECT 1 FROM decisions WHERE claim_id = ?", (claim_id,)
    ).fetchone():
        raise HTTPException(409, "Claim already has a decision")
    approved = body.decision == "approve"
    if approved != (body.payout > 0):
        raise HTTPException(
            422, "Only an approval has a payout, and it must be above 0"
        )
    conn.execute(
        "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?)",
        (
            claim_id,
            body.decision,
            round(body.payout, 2),
            body.explanation,
            body.policy_section,
            now(),
        ),
    )
    over_limit = body.payout > db.company()["payout_approval_limit"]
    if not approved:
        status = "decided"
    elif over_limit:
        status = "waiting_for_signoff"
    else:
        status = "in_progress"
    set_status(conn, claim_id, status)
    conn.commit()
    return {"status": status}


def pay(conn: sqlite3.Connection, claim_id: str, amount: float) -> dict[str, Any]:
    """Pay an approved claim, unless the rules block it."""
    decision = conn.execute(
        "SELECT decision, payout FROM decisions WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if decision is None or decision["decision"] != "approve":
        raise HTTPException(409, "Claim has no approved decision")
    if conn.execute(
        "SELECT 1 FROM payments WHERE claim_id = ?", (claim_id,)
    ).fetchone():
        raise HTTPException(409, "Claim is already paid")
    if round(amount, 2) != decision["payout"]:
        raise HTTPException(409, f"Amount must be the payout, {decision['payout']:.2f}")
    signed = conn.execute(
        "SELECT 1 FROM signoffs WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if decision["payout"] > db.company()["payout_approval_limit"] and not signed:
        raise HTTPException(
            409, "Payout is over the approval limit and needs a handler's sign-off"
        )
    conn.execute(
        "INSERT INTO payments VALUES (?, ?, ?)", (claim_id, decision["payout"], now())
    )
    set_status(conn, claim_id, "decided")
    conn.commit()
    return {"status": "decided", "paid": decision["payout"]}


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, body: PaymentBody, conn: Conn) -> dict[str, Any]:
    """Pay a claim the amount of its approved payout."""
    claim_row(conn, claim_id)
    return pay(conn, claim_id, body.amount)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, body: SignOffBody, conn: Conn) -> dict[str, Any]:
    """Sign off a claim as a handler and pay it."""
    claim = claim_row(conn, claim_id)
    record(conn, "handler", body.handler_id)
    if claim["status"] != "waiting_for_signoff":
        raise HTTPException(409, f"Claim is {claim['status']}")
    conn.execute(
        "INSERT INTO signoffs VALUES (?, ?, ?)", (claim_id, body.handler_id, now())
    )
    amount = conn.execute(
        "SELECT payout FROM decisions WHERE claim_id = ?", (claim_id,)
    ).fetchone()["payout"]
    return pay(conn, claim_id, amount)


@app.post("/api/claims/{claim_id}/events", operation_id="add_event")
def add_event(claim_id: str, body: EventBody, conn: Conn) -> dict[str, int]:
    """Add one step of the agent's work to a claim."""
    claim_row(conn, claim_id)
    cursor = conn.execute(
        "INSERT INTO events (claim_id, tool, input, result, at) VALUES (?, ?, ?, ?, ?)",
        (claim_id, body.tool, body.input, body.result, now()),
    )
    conn.commit()
    return {"id": cursor.lastrowid or 0}


def log_event(claim_id: str, tool: str, result: str) -> None:
    """Add a step to a claim from the backend itself."""
    with closing(db.connect()) as conn:
        conn.execute(
            "INSERT INTO events (claim_id, tool, input, result, at)"
            " VALUES (?, ?, '', ?, ?)",
            (claim_id, tool, result, now()),
        )
        conn.commit()


def work_claim(claim_id: str) -> None:
    """Run the agent on a claim; return it to the queue if it decides nothing."""
    try:
        run_agent(claim_id, f"{claim_id}-{uuid4().hex[:8]}")
    except Exception as error:
        log_event(claim_id, "error", f"The agent failed: {error}")
    with closing(db.connect()) as conn:
        claim = claim_row(conn, claim_id)
        undecided = not conn.execute(
            "SELECT 1 FROM decisions WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        if claim["status"] == "in_progress" and undecided:
            set_status(conn, claim_id, "waiting")
            conn.commit()


@app.post("/api/claims/{claim_id}/run", operation_id="run_claim_agent")
def run_claim_agent(
    claim_id: str, background: BackgroundTasks, conn: Conn
) -> dict[str, str]:
    """Start the agent on a waiting claim."""
    claim = claim_row(conn, claim_id)
    if claim["status"] != "waiting":
        raise HTTPException(409, f"Claim is {claim['status']}")
    set_status(conn, claim_id, "in_progress")
    conn.commit()
    background.add_task(work_claim, claim_id)
    return {"status": "in_progress"}
