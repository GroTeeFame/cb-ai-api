from __future__ import annotations

from typing import Any, Dict, Optional

from app.schemas.state import ConversationState
from app.tools.types import ToolExecutionResult


def lookup_client_balances(
    *,
    client_id: Optional[int],
    state: Optional[ConversationState],
    language: Optional[str],
) -> ToolExecutionResult:
    """
    Indicate that the chatbot backend should present account balances.

    The legacy system already holds every parameter (client id, auth state, etc.),
    so the AI agent simply declares the intent.
    """
    return ToolExecutionResult(
        event="function",
        data="get_balances",
        context_updates={},
    )


def lookup_total_balance(
    *,
    client_id: Optional[int],
    state: Optional[ConversationState],
    language: Optional[str],
) -> ToolExecutionResult:
    """
    Indicate that the chatbot backend should compute the total balance.
    """
    return ToolExecutionResult(
        event="function",
        data="get_total_balance",
        context_updates={},
    )


BALANCE_TOOLS: list[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_client_balances",
            "description": (
                "Request the legacy chatbot backend to look up account balances "
                "for a banking client in the demo dataset. Provide the numeric "
                "client_id if known; otherwise the stored value will be used."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_total_balance",
            "description": (
                "Request the legacy chatbot backend to summarize the total balance "
                "across all accounts for a client in the demo dataset."
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
