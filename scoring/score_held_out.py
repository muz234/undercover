"""Score the UnderCover Agent on the held-out claims.

Runs the agent through the real backend on a temporary database that holds the
held-out claims, then compares its decisions with the handlers' answer key.
The answer key is read only after every run has finished, and never reaches the
backend or the agent.

    uv run scoring/score_held_out.py
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "data" / "evals"
PORT = "8100"
URL = f"http://localhost:{PORT}"
WORKERS = 1
TIMEOUT = 600


def load_held_out_claims(db_path: Path) -> list[str]:
    """Replace the queue in a fresh database with the held-out claims."""
    os.environ["UNDERCOVER_DB"] = str(db_path)
    sys.path.insert(0, str(ROOT))
    from backend import db

    conn = db.connect()
    conn.execute("DELETE FROM claims")
    claims = json.loads((EVALS / "held_out_claims.json").read_text("utf-8"))
    for claim in claims:
        claim.pop("status")
        conn.execute(
            "INSERT INTO claims VALUES (?, 'waiting', ?)",
            (claim["claim_id"], json.dumps(claim)),
        )
    conn.commit()
    conn.close()
    return [claim["claim_id"] for claim in claims]


def run_claim(claim_id: str) -> dict:
    """Run the agent on one claim and return the claim once it settles."""
    with httpx.Client(base_url=URL, timeout=30) as client:
        client.post(f"/api/claims/{claim_id}/run").raise_for_status()
        start = time.time()
        while True:
            time.sleep(3)
            claim = client.get(f"/api/claims/{claim_id}").json()
            if claim["status"] != "in_progress" or time.time() - start > TIMEOUT:
                return claim


def main() -> None:
    db_path = Path(tempfile.mkdtemp()) / "held_out.db"
    ids = load_held_out_claims(db_path)
    server = subprocess.Popen(
        ["uv", "run", "-m", "uvicorn", "backend.main:app", "--port", PORT],
        cwd=ROOT,
        env={
            **os.environ,
            "UNDERCOVER_DB": str(db_path),
            "UNDERCOVER_BACKEND_URL": URL,
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        while True:
            try:
                httpx.get(f"{URL}/api/health").raise_for_status()
                break
            except httpx.HTTPError:
                time.sleep(1)
        with ThreadPoolExecutor(WORKERS) as pool:
            results = dict(zip(ids, pool.map(run_claim, ids), strict=True))
    finally:
        server.terminate()
    score(results)


def score(results: dict[str, dict]) -> None:
    """Compare the agent's decisions with the answer key and print the scores."""
    key = {
        d["claim_id"]: d
        for d in json.loads((EVALS / "held_out_decisions.json").read_text("utf-8"))
    }
    rows = []
    for claim_id, claim in results.items():
        got = claim["decision"]
        want = key[claim_id]
        decision = got["decision"] if got else "none"
        payout = got["payout"] if got else 0.0
        rows.append(
            {
                "claim_id": claim_id,
                "want": want["decision"],
                "got": decision,
                "want_payout": want["payout"],
                "got_payout": payout,
                "decision_ok": decision == want["decision"],
                "payout_ok": abs(payout - want["payout"]) < 0.01,
                "status": claim["status"],
                "difficulty": want["difficulty"],
                "tests": want["tests"],
                "reason": got["explanation"] if got else "",
            }
        )
    (ROOT / "scoring" / "held_out_results.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8"
    )
    total = len(rows)
    for row in rows:
        mark = "ok " if row["decision_ok"] and row["payout_ok"] else "BAD"
        print(
            f"{mark} {row['claim_id']} want {row['want']} {row['want_payout']:.2f}"
            f" got {row['got']} {row['got_payout']:.2f} [{row['difficulty']}]"
        )
    both = sum(r["decision_ok"] and r["payout_ok"] for r in rows)
    print(f"\nDecision correct: {sum(r['decision_ok'] for r in rows)}/{total}")
    print(f"Payout correct:   {sum(r['payout_ok'] for r in rows)}/{total}")
    print(f"Both correct:     {both}/{total}")
    by_level: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        by_level[row["difficulty"]].append(row["decision_ok"] and row["payout_ok"])
    for level, oks in sorted(by_level.items()):
        print(f"  {level}: {sum(oks)}/{len(oks)}")


if __name__ == "__main__":
    main()
