from __future__ import annotations

from typing import Any, Dict, Optional

from app.schemas.state import ConversationState
from app.tools.types import ToolExecutionResult


def get_exchange(
    *,
    client_id: Optional[int],
    state: Optional[ConversationState],
    language: Optional[str],
) -> ToolExecutionResult:
    """
    Indicate that the chatbot backend should present currency exchange rate to client.

    The legacy system already holds every parameter, so the AI agent simply declares the intent.
    """
    return ToolExecutionResult(
        event="function",
        data="get_exchange",
        context_updates={}
    )



CURRENCY_TOOLS: list[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_exchange",
            "description": (
                "Request the legacy chatbot backend to send current bank exchange rate to client."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]