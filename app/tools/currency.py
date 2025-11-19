from __future__ import annotations

from typing import Any, Dict, Optional

import requests
import logging

from app.schemas.state import ConversationState
from app.tools.types import ToolExecutionResult

logger = logging.getLogger(__name__)

BANK_API_BASE_URL = "http://10.129.132.15:8000"


def _language_bundle(language: Optional[str]) -> Dict[str, str]:
    if language and language.lower().startswith("en"):
        return {
            "missing_id": "I need the client ID to look up balances.",
            "no_accounts": "I couldn't find any accounts for this client.",
            "error": "I cannot retrieve balance information right now.",
        }
    return {
        "missing_id": "Щоб переглянути баланси, потрібен ідентифікатор клієнта.",
        "no_accounts": "Для цього клієнта не знайдено рахунків.",
        "error": "Наразі не можу отримати дані про баланси.",
    }


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
        context_updates={},
        post_process=False,
    )

def get_specific_exchange(
    *,
    client_id: Optional[int],
    state: Optional[ConversationState],
    language: Optional[str],
) -> ToolExecutionResult:
    """
    Get list with current bank exchange rate, to give answer to user with LLM.
    """
    # http://10.129.132.15:8000/api/chatbot/get_exchangeRate
    strings = _language_bundle(language)

    try: 
        response = requests.get(
            f"{BANK_API_BASE_URL}/api/chatbot/get_exchangeRate",
            proxies={
                "http": None,
                "https": None,
            },
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        logger.warning("get_specific_exchange() failed: %s", exc)
        #TODO: here we can use two solution, we can send error to chatbot -> client.
        #TODO: or we not send error, instead we send to chatbot command to execute this from its beckend
        # return ToolExecutionResult(event='send', data=strings["error"])
        return ToolExecutionResult(
            event='function', 
            data="get_exchange",
            context_updates={},
            post_process=False,
        )
    if not payload:
        return ToolExecutionResult(
            event='function', 
            data="get_exchange",
            context_updates={},
            post_process=False,
        )
    return ToolExecutionResult(
            event='send', 
            data=payload,
            context_updates={},
            post_process=True,
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
    {
        "type": "function",
        "function": {
            "name": "get_specific_exchange",
            "description": (
                "Request list of current bank exchange rates, to give give user answer about specific currency exchange rate with LLM processing."
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