from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests
import logging

from app.schemas.state import ConversationState
from app.tools.types import ToolExecutionResult

logger = logging.getLogger(__name__)

BANK_API_BASE_URL = "http://10.129.132.15:8000"

CLIENT_SERVICE_BASE_URL = "http://127.0.0.1:8001"
# CLIENT_SERVICE_BASE_URL = "http://127.0.0.1:8001"


# def _resolve_client_id(
#     provided_id: Optional[int],
#     state: Optional[ConversationState],
# ) -> Optional[int]:
#     if provided_id is not None:
#         return int(provided_id)
#     if state:
#         stored = state.slots.get("client_id")
#         if stored is not None:
#             try:
#                 return int(stored)
#             except (TypeError, ValueError):
#                 return None
#     return None


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


def get_balance(
    *,
    client_id: Optional[int],
    state: Optional[ConversationState],
    language: Optional[str],
) -> ToolExecutionResult:
    """
    Indicate that the chatbot backend should find and present client balance to client.

    The legacy system already holds every parameter, so the AI agent simply declares the intent.
    """
    return ToolExecutionResult(
        event="function",
        data="get_balance",
        context_updates={},
        post_process=False,
    )

def get_specific_balance(
    *,
    client_id: int,
    state: Optional[ConversationState],
    language: Optional[str],
) -> ToolExecutionResult:
    """
    Get list with all accounts and its balances, to give answer to user with LLM.
    """

    logger.info(f"get_specific_balance() : client_id={client_id}")

    try:
        body = {
            "mode": 0,
            "clientid": client_id,
        },
        logger.info(f"get_specific_balance() : body={body}")
        response = requests.get(
            f"{BANK_API_BASE_URL}/api/chatbot/accounts",
            # f"{CLIENT_SERVICE_BASE_URL}/accounts",
            data=body,
            proxies={
                "http": None,
                "https": None,
            },
            headers={"Content-Type": "application/json"},
            timeout=20,
        )
        
        logger.info(f"get_specific_balance() : response={response}")
        response.raise_for_status()
        payload = response.json()
        logger.info(f"get_specific_balance() : payload={payload}")

    except requests.RequestException as exc:
        logger.warning("get_specific_exchange() failed: %s", exc)
        #TODO: here we can use two solution, we can send error to chatbot -> client.
        #TODO: or we not send error, instead we send to chatbot command to execute this from its beckend
        # return ToolExecutionResult(event='send', data=strings["error"])
        
        return ToolExecutionResult(
            event='function',
            data='get_balance',
            context_updates={},
            post_process=False,
        )
    if not payload:
        return ToolExecutionResult(
            event='function',
            data='get_balance',
            context_updates={},
            post_process=False,
        )
    return ToolExecutionResult(
        event='send',
        data=payload,
        context_updates={},
        post_process=True,
    )


BALANCE_TOOLS: list[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_balance",
            "description": (
                "Request the legacy chatbot backend to find and send current account balance to client."
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
            "name": "get_specific_balance",
            "description": (
                "Request the list with all user accounts and balances to give user answers about specific account and balance. with LLM processing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "integer",
                        "description": (
                            "Identifier of kind of search for account/balance search."
                        )
                    },
                    "client_id": {
                        "type": "integer",
                        "description": (
                            "Identifier of the client in bank database"
                        ),
                    }
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]

# def lookup_client_balances(
#     *,
#     client_id: Optional[int],
#     state: Optional[ConversationState],
#     language: Optional[str],
# ) -> ToolExecutionResult:
#     """Fetch per-account balances via the demo banking API."""
#     strings = _language_bundle(language)
#     # resolved_id = _resolve_client_id(client_id, state)
#     # if resolved_id is None:
#     #     return ToolExecutionResult(event="send", data=strings["missing_id"])
#     resolved_id = 5
#     try:
#         response = requests.get(
#             f"{CLIENT_SERVICE_BASE_URL}/client_balances",
#             params={"client_id": resolved_id},
#             headers={"Content-Type": "application/json"},
#             timeout=5,
#         )
#         response.raise_for_status()
#         payload = response.json()
#     except requests.RequestException as exc:
#         logger.warning("Balance lookup failed for client %s: %s", resolved_id, exc)
#         return ToolExecutionResult(event="send", data=strings["error"])

#     accounts: List[Dict[str, Any]] = payload.get("accounts") if isinstance(payload, dict) else []
#     if not accounts:
#         return ToolExecutionResult(
#             event="send",
#             data=strings["no_accounts"],
#             context_updates={"slots": {"client_id": resolved_id}},
#         )

#     structured_reply = {
#         "type": "accounts",
#         "client_id": resolved_id,
#         "accounts": accounts,
#     }
#     return ToolExecutionResult(
#         event="send",
#         data=structured_reply,
#         # context_updates={"slots": {"client_id": resolved_id}},
#         context_updates={},
#         post_process=True,
#     )



# def lookup_total_balance(
#     *,
#     client_id: Optional[int],
#     state: Optional[ConversationState],
#     language: Optional[str],
# ) -> ToolExecutionResult:
#     """Fetch aggregate balance for a client via the demo banking API."""
#     strings = _language_bundle(language)
#     # resolved_id = _resolve_client_id(client_id, state)
#     # if resolved_id is None:
#     #     return ToolExecutionResult(event="send", data=strings["missing_id"])
#     resolved_id = 5
#     try:
#         response = requests.get(
#             f"{CLIENT_SERVICE_BASE_URL}/client_total_balance",
#             params={"client_id": resolved_id},
#             headers={"Content-Type": "application/json"},
#             timeout=5,
#         )
#         response.raise_for_status()
#         payload = response.json()
#     except requests.RequestException as exc:
#         logger.warning("Total balance lookup failed for client %s: %s", resolved_id, exc)
#         return ToolExecutionResult(event="send", data=strings["error"])

#     total_value: Optional[float]
#     if isinstance(payload, dict):
#         total_value = payload.get("total_balance")
#     else:
#         total_value = payload

#     if total_value is None:
#         return ToolExecutionResult(event="send", data=strings["error"])

#     structured_reply = {
#         "type": "total_balance",
#         "client_id": resolved_id,
#         "total": total_value,
#     }
#     logger.info(
#         "TOOL USAGE lookup_total_balance calling to api with next result: %s",
#         total_value,
#     )
#     return ToolExecutionResult(
#         event="send",
#         data=structured_reply,
#         context_updates={"slots": {"client_id": resolved_id}},
#         post_process=True,
#     )


# BALANCE_TOOLS: list[Dict[str, Any]] = [
#     {
#         "type": "function",
#         "function": {
#             "name": "lookup_client_balances",
#             "description": (
#                 "Request the legacy chatbot backend to look up account balances "
#                 "for a banking client in the demo dataset. Provide the numeric "
#                 "client_id if known; otherwise the stored value will be used."
#             ),
#             "parameters": {
#                 "type": "object",
#                 "properties": {},
#                 "required": [],
#                 "additionalProperties": False,
#             },
#         },
#     },
#     {
#         "type": "function",
#         "function": {
#             "name": "lookup_total_balance",
#             "description": (
#                 "Request the legacy chatbot backend to summarize the total balance "
#                 "across all accounts for a client in the demo dataset."
#             ),
#             "parameters": {
#                 "type": "object",
#                 "properties": {},
#                 "required": [],
#                 "additionalProperties": False,
#             },
#         },
#     },
# ]
