from __future__ import annotations

from typing import Any, Dict, Optional

from app.schemas.state import ConversationState
from app.tools.types import ToolExecutionResult
import logging

logger = logging.getLogger(__name__)


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
    #TODO: Its working schema. Tools will be used in this way. But i need to make clear to agent when and what tool to use
    #TODO: Now i need to add one more tool to call BURA api, to get exchange rate, in case if user want to know exact currency.
    #TODO: Or i need to make call to BURA api every time when user want to know exchange rate, but when user want exact currency agent give him only those currency.

    # import requests
    # try:
    #     response = requests.get(
    #         f"http://127.0.0.1:8001/client_total_balance",
    #         params={"client_id": 5},
    #         headers={"Content-Type": "application/json"},
    #         timeout=5,
    #     )
    #     if response.status_code == 200:
    #         payload = response.json()
    #         if isinstance(payload, dict):
    #             total = payload.get("total_balance")
    #         else:
    #             total = payload
    #     else:
    #         response.raise_for_status()
    # except requests.RequestException:
    #     total = None
    # logger.info(
    #     f"TOOL USAGE lookup_total_balance calling to api with next result: {total}",
    #     extra={},
    # )


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
