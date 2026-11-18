"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

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
