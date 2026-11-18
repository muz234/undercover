import builtins
import pathlib

from fastapi.testclient import TestClient

from backend import db
from backend.main import app

client = TestClient(app)


def test_queue():
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    assert {claim["status"] for claim in claims} == {"waiting"}
    assert claims[0]["customer_name"] == "Maya Patel"


def test_claim():
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["policy_id"] == "POL-2001"
    assert len(claim["items"]) == 3
    assert claim["decision"] is None
    assert claim["events"] == []


def test_records():
    assert client.get("/api/policies/POL-2001").json()["plan"] == "premium"
    history = client.get("/api/customers/CUS-3001").json()["previous_claims"]
    assert history[0]["claim_id"] == "CLM-0412"
    assert client.get("/api/plans/premium").json()["deductible"] == 50
    assert len(client.get("/api/handlers").json()) == 3
    assert client.get("/api/company").json()["payout_approval_limit"] == 1000


def test_documents():
    assert "Policy Wording" in client.get("/api/policy-wording").json()["text"]
    assert client.get("/api/instructions").json()["text"]


def test_missing():
    assert client.get("/api/claims/CLM-0000").status_code == 404
    assert client.get("/api/policies/nope").status_code == 404


def test_restart_keeps_data():
    first = client.get("/api/claims").json()
    db.connect().close()
    assert client.get("/api/claims").json() == first


def test_seed_never_opens_evals(monkeypatch):
    opened: list[str] = []
    real_open = builtins.open
    real_read = pathlib.Path.read_text

    def spy_open(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    def spy_read(self, *args, **kwargs):
        opened.append(str(self))
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(pathlib.Path, "read_text", spy_read)
    client.get("/api/claims")
    client.get("/api/policy-wording")
    assert any("claims.json" in path for path in opened)
    assert not any("evals" in path or "security" in path for path in opened)


def test_operations_have_ids_and_no_optional_inputs():
    spec = client.get("/api/openapi.json").json()
    schemas = spec["components"].get("schemas", {})
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            assert operation.get("operationId"), (path, method)
            assert operation.get("summary") or operation.get("description")
            assert all(p["required"] for p in operation.get("parameters", []))
            body = operation.get("requestBody")
            if body:
                ref = body["content"]["application/json"]["schema"]["$ref"]
                schema = schemas[ref.split("/")[-1]]
                assert set(schema["required"]) == set(schema["properties"])


def test_instructions_cover_the_rules():
    text = client.get("/api/instructions").json()["text"]
    for phrase in ("record_decision", "pay_claim", "$1,000.00", "sign off", "wording"):
        assert phrase in text
