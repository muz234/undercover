"""SQLite storage, seeded from data/."""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    kind TEXT NOT NULL,
    id TEXT NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (kind, id)
);
CREATE TABLE IF NOT EXISTS decisions (
    claim_id TEXT PRIMARY KEY,
    decision TEXT NOT NULL,
    payout REAL NOT NULL,
    explanation TEXT NOT NULL,
    policy_section TEXT NOT NULL,
    decided_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signoffs (
    claim_id TEXT PRIMARY KEY,
    handler_id TEXT NOT NULL,
    signed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    claim_id TEXT PRIMARY KEY,
    amount REAL NOT NULL,
    paid_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    input TEXT NOT NULL,
    result TEXT NOT NULL,
    at TEXT NOT NULL
);
"""

# (kind, file, key in the file or None for a list, id field)
RECORDS = [
    ("policy", "policies.json", None, "policy_id"),
    ("customer", "customers.json", None, "customer_id"),
    ("handler", "handlers.json", None, "handler_id"),
    ("plan", "plans.json", "plans", "plan"),
]


def load_json(name: str) -> Any:
    """Read a JSON file from data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def company() -> dict[str, Any]:
    """Return the company settings."""
    return load_json("company.json")


def policy_wording() -> str:
    """Return the policy wording."""
    return (DATA / "policy_wording.md").read_text(encoding="utf-8")


def seed(conn: sqlite3.Connection) -> None:
    """Load the claims, policies, customers, handlers and plans."""
    for claim in load_json("claims.json"):
        claim.pop("status")
        conn.execute(
            "INSERT OR IGNORE INTO claims VALUES (?, 'waiting', ?)",
            (claim["claim_id"], json.dumps(claim)),
        )
    for kind, name, key, id_field in RECORDS:
        content = load_json(name)
        rows = content[key] if key else content
        for row in rows:
            conn.execute(
                "INSERT OR IGNORE INTO records VALUES (?, ?, ?)",
                (kind, row[id_field], json.dumps(row)),
            )
    conn.commit()


def connect() -> sqlite3.Connection:
    """Open the database, creating and seeding it when empty."""
    path = Path(os.getenv("UNDERCOVER_DB") or ROOT / "undercover.db")
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0:
        seed(conn)
    return conn
