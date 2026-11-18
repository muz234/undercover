from fastapi.testclient import TestClient

from backend import main
from backend.main import app

client = TestClient(app)


def status(claim_id="CLM-1001"):
    return client.get(f"/api/claims/{claim_id}").json()


def test_run_starts_the_agent(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "run_agent", lambda *args: calls.append(args))
    assert client.post("/api/claims/CLM-1001/run").json() == {"status": "in_progress"}
    assert calls[0][0] == "CLM-1001"
    assert calls[0][1].startswith("CLM-1001-")
    claim = status()
    assert claim["status"] == "waiting"
    assert "did not finish" in claim["events"][0]["result"]


def test_run_refused_when_not_waiting():
    client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "decline",
            "payout": 0,
            "explanation": "x",
            "policy_section": "9",
        },
    )
    assert client.post("/api/claims/CLM-1001/run").status_code == 409
    assert client.post("/api/claims/CLM-0000/run").status_code == 404


def test_crash_returns_the_claim_to_the_queue(monkeypatch):
    def boom(*args):
        raise RuntimeError("model offline")

    monkeypatch.setattr(main, "run_agent", boom)
    client.post("/api/claims/CLM-1001/run")
    claim = status()
    assert claim["status"] == "waiting"
    assert claim["events"][0]["tool"] == "error"
    assert "model offline" in claim["events"][0]["result"]


def test_decided_claim_stays_decided(monkeypatch):
    def decide(claim_id, thread_id):
        client.post(
            f"/api/claims/{claim_id}/decision",
            json={
                "decision": "refer",
                "payout": 0,
                "explanation": "x",
                "policy_section": "11",
            },
        )

    monkeypatch.setattr(main, "run_agent", decide)
    client.post("/api/claims/CLM-1001/run")
    assert status()["status"] == "decided"


def test_half_finished_run_is_rolled_back(monkeypatch):
    def decide_then_crash(claim_id, thread_id):
        client.post(
            f"/api/claims/{claim_id}/decision",
            json={
                "decision": "approve",
                "payout": 100,
                "explanation": "x",
                "policy_section": "3",
            },
        )
        raise RuntimeError("rate limited")

    monkeypatch.setattr(main, "run_agent", decide_then_crash)
    client.post("/api/claims/CLM-1001/run")
    claim = status()
    assert claim["status"] == "waiting"
    assert claim["decision"] is None
    assert "rate limited" in claim["events"][0]["result"]
    monkeypatch.setattr(main, "run_agent", lambda *args: None)
    assert client.post("/api/claims/CLM-1001/run").status_code == 200
