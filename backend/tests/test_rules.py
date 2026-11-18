import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def decide(claim_id="CLM-1001", decision="approve", payout=420.0):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "explanation": "Because.",
            "policy_section": "3",
        },
    )


def pay(claim_id="CLM-1001", amount=420.0):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def status(claim_id="CLM-1001"):
    return client.get(f"/api/claims/{claim_id}").json()["status"]


def test_small_approval_is_paid():
    assert decide().json() == {"status": "in_progress"}
    assert pay().status_code == 200
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["payout"] == 420.0
    assert claim["payment"]["amount"] == 420.0
    assert pay().status_code == 409


def test_exactly_the_limit_is_paid_without_sign_off():
    decide(payout=1000.0)
    assert pay(amount=1000.0).status_code == 200
    assert status() == "decided"


def test_payment_blocked_until_sign_off():
    assert decide(payout=1250.0).json() == {"status": "waiting_for_signoff"}
    assert pay(amount=1250.0).status_code == 409
    assert client.get("/api/claims/CLM-1001").json()["payment"] is None
    assert status() == "waiting_for_signoff"
    done = client.post("/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-01"})
    assert done.status_code == 200
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 1250.0
    assert claim["signoff"]["handler_id"] == "HND-01"
    again = client.post("/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-02"})
    assert again.status_code == 409


def test_decline_and_refer_are_decided():
    assert decide(decision="decline", payout=0).json() == {"status": "decided"}
    assert decide("CLM-1002", "refer", 0).json() == {"status": "decided"}
    assert pay(amount=0).status_code == 409


@pytest.mark.parametrize(
    ("decision", "payout"), [("approve", 0), ("approve", -5), ("decline", 10)]
)
def test_bad_payouts_are_rejected(decision, payout):
    assert decide(decision=decision, payout=payout).status_code == 422
    assert status() == "waiting"


def test_second_decision_is_refused():
    decide()
    assert decide().status_code == 409


def test_pay_needs_an_approved_decision_and_the_right_amount():
    assert pay().status_code == 409
    decide()
    assert pay(amount=999.0).status_code == 409
    assert status() == "in_progress"


def test_sign_off_refusals():
    sign = "/api/claims/CLM-1001/sign-off"
    assert client.post(sign, json={"handler_id": "HND-01"}).status_code == 409
    decide(payout=2000.0)
    assert client.post(sign, json={"handler_id": "HND-99"}).status_code == 404
    assert client.get("/api/claims/CLM-1001").json()["signoff"] is None


def test_decisions_are_per_claim():
    decide()
    assert client.get("/api/claims/CLM-1002").json()["decision"] is None


def test_events_are_ordered():
    for tool in ("get_claim", "get_policy"):
        body = {"tool": tool, "input": "{}", "result": "ok"}
        assert client.post("/api/claims/CLM-1001/events", json=body).status_code == 200
    events = client.get("/api/claims/CLM-1001").json()["events"]
    assert [event["tool"] for event in events] == ["get_claim", "get_policy"]
    body = {"tool": "x", "input": "", "result": ""}
    assert client.post("/api/claims/CLM-0000/events", json=body).status_code == 404
