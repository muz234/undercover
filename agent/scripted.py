"""A scripted model for end-to-end tests: it approves the amount claimed."""

import json
from typing import Any
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedModel(BaseChatModel):
    """Reads the claim, approves what was claimed, pays, and reports."""

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedModel":
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        claim_id = str(messages[1].content).split()[-1].rstrip(".")
        results = [m for m in messages if isinstance(m, ToolMessage)]
        claimed = json.loads(results[0].text)["amount_claimed"] if results else 0
        script = [
            ("get_claim", {"claim_id": claim_id}),
            (
                "record_decision",
                {
                    "claim_id": claim_id,
                    "decision": "approve",
                    "payout": claimed,
                    "explanation": "Scripted approval of the amount claimed.",
                    "policy_section": "Section 3, Trip Delay",
                },
            ),
            ("pay_claim", {"claim_id": claim_id, "amount": claimed}),
        ]
        if len(results) < len(script):
            name, args = script[len(results)]
            message = AIMessage(
                content="",
                tool_calls=[{"name": name, "args": args, "id": uuid4().hex}],
            )
        else:
            message = AIMessage(content="Decision recorded.")
        return ChatResult(generations=[ChatGeneration(message=message)])
