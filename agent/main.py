"""The UnderCover Agent."""

import os
from typing import Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from agent.scripted import ScriptedModel
from agent.steps import StepLogger

load_dotenv(override=True)

BACKEND_URL = os.getenv("UNDERCOVER_BACKEND_URL", "http://localhost:8000")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, path: str, body: dict | None = None) -> str:
    """Call the backend and return the reply, or the error for the agent to read."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_error:
        return f"Error {response.status_code}: {response.text}"
    return response.text


@tool
def get_claim(claim_id: str) -> str:
    """Get a claim: the story, the items claimed and the documents."""
    return call("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> str:
    """Get a policy: the plan, add-ons, trip dates, trip cost and travelers."""
    return call("GET", f"/api/policies/{policy_id}")


@tool
def get_plan(plan: str) -> str:
    """Get a plan's limits, waiting periods and deductible."""
    return call("GET", f"/api/plans/{plan}")


@tool
def get_customer(customer_id: str) -> str:
    """Get a customer and their claim history."""
    return call("GET", f"/api/customers/{customer_id}")


@tool
def get_policy_wording() -> str:
    """Get the policy wording, the contract that decides every claim."""
    return call("GET", "/api/policy-wording")


@tool
def get_claims_manual() -> str:
    """Get the claims manual: how UnderCover applies the wording and handles claims."""
    return call("GET", "/api/claims-manual")


@tool
def record_decision(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    explanation: str,
    policy_section: str,
) -> str:
    """Record the decision on a claim. The payout is 0 unless approving."""
    body = {
        "decision": decision,
        "payout": payout,
        "explanation": explanation,
        "policy_section": policy_section,
    }
    return call("POST", f"/api/claims/{claim_id}/decision", body)


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay an approved claim its payout. Over $1,000.00 needs a handler's sign-off."""
    return call("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})


TOOLS = [
    get_claim,
    get_policy,
    get_plan,
    get_customer,
    get_policy_wording,
    get_claims_manual,
    record_decision,
    pay_claim,
]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
        max_retries=10,
    )


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Decide one claim and return the agent's final reply."""
    with backend() as client:
        instructions = client.get("/api/instructions").raise_for_status().json()["text"]
    if llm is None and os.getenv("UNDERCOVER_SCRIPTED_MODEL"):
        llm = ScriptedModel()
    agent = create_agent(llm or model(), tools=TOOLS, system_prompt=instructions)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"Decide claim {claim_id}."}]},
        config={
            "configurable": {"thread_id": thread_id},
            "callbacks": [StepLogger(claim_id, backend)],
        },
    )
    return result["messages"][-1].text
