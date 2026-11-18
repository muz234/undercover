"""Reports each tool call the agent makes to the backend."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

import httpx
from langchain_core.callbacks import BaseCallbackHandler


class StepLogger(BaseCallbackHandler):
    """Posts each tool call and its result to the backend as a step of the claim."""

    def __init__(self, claim_id: str, client: Callable[[], httpx.Client]) -> None:
        self.claim_id = claim_id
        self.client = client
        self.started: dict[UUID, tuple[str, str]] = {}

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self.started[run_id] = (kwargs.get("name") or serialized["name"], input_str)

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        tool, tool_input = self.started.pop(run_id)
        with self.client() as client:
            client.post(
                f"/api/claims/{self.claim_id}/events",
                json={
                    "tool": tool,
                    "input": tool_input,
                    "result": str(getattr(output, "content", output)),
                },
            ).raise_for_status()
