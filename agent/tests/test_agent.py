import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend.main import app

client = TestClient(app)


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def call(name, **args):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": f"{name}-1"}]
    )


def decision(payout, decision="approve"):
    return call(
        "record_decision",
        claim_id="CLM-1001",
        decision=decision,
        payout=payout,
        explanation="Covered.",
        policy_section="Section 3, Trip Delay",
    )


def run_script(monkeypatch, *replies):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    stub = StubModel(messages=iter(replies))
    return main.run("CLM-1001", "thread-1", stub)


def test_read_tools(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    assert "CLM-1001" in main.get_claim.invoke({"claim_id": "CLM-1001"})
    assert "premium" in main.get_policy.invoke({"policy_id": "POL-2001"})
    assert "deductible" in main.get_plan.invoke({"plan": "premium"})
    assert "CLM-0412" in main.get_customer.invoke({"customer_id": "CUS-3001"})
    assert "Policy Wording" in main.get_policy_wording.invoke({})
    assert "Claims Handling Manual" in main.get_claims_manual.invoke({})
    assert main.get_claim.invoke({"claim_id": "CLM-0000"}).startswith("Error 404")


def test_small_approval_is_paid(monkeypatch):
    reply = run_script(
        monkeypatch,
        call("get_claim", claim_id="CLM-1001"),
        decision(420.0),
        call("pay_claim", claim_id="CLM-1001", amount=420.0),
        AIMessage(content="Approved $420.00 and paid."),
    )
    assert reply == "Approved $420.00 and paid."
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 420.0
    assert [event["tool"] for event in claim["events"]] == [
        "get_claim",
        "record_decision",
        "pay_claim",
    ]
    assert "CLM-1001" in claim["events"][0]["input"]


def test_large_payment_is_blocked(monkeypatch):
    run_script(
        monkeypatch,
        decision(1250.0),
        call("pay_claim", claim_id="CLM-1001", amount=1250.0),
        AIMessage(content="Waiting for sign-off."),
    )
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "waiting_for_signoff"
    assert claim["payment"] is None
    assert "Error 409" in claim["events"][-1]["result"]


def test_instructions_come_from_the_backend(monkeypatch):
    seen = []

    class Spy(StubModel):
        def _generate(self, messages, *args, **kwargs):
            seen.append(messages[0].content)
            return super()._generate(messages, *args, **kwargs)

    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    main.run("CLM-1001", "t", Spy(messages=iter([AIMessage(content="Done.")])))
    assert seen[0] == client.get("/api/instructions").json()["text"]


@pytest.mark.parametrize("tool", main.TOOLS)
def test_tools_have_docstrings_and_no_optional_inputs(tool):
    assert tool.description
    schema = tool.args_schema.model_json_schema()
    assert set(schema.get("required", [])) == set(schema["properties"])


def test_agent_only_talks_to_the_backend():
    source = "".join(
        path.read_text() for path in Path(main.__file__).parent.glob("*.py")
    )
    assert not re.search(r"evals|sqlite|data/|\.json\"", source)


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"


def test_scripted_model_decides_and_pays(monkeypatch):
    monkeypatch.setenv("UNDERCOVER_SCRIPTED_MODEL", "1")
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    assert main.run("CLM-1001", "t") == "Decision recorded."
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 420.0


def test_scripted_model_waits_for_sign_off_on_a_large_claim(monkeypatch):
    monkeypatch.setenv("UNDERCOVER_SCRIPTED_MODEL", "1")
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    main.run("CLM-1002", "t")
    claim = client.get("/api/claims/CLM-1002").json()
    assert claim["status"] == "waiting_for_signoff"
    assert claim["payment"] is None
