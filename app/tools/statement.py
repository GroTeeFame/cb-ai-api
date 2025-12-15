from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
import json
import logging
import requests
import datetime

from app.schemas.state import ConversationState
from app.tools.types import ToolExecutionResult

logger = logging.getLogger(__name__)

BANK_API_BASE_URL = "http://10.129.132.15:8000"

CLIENT_SERVICE_BASE_URL = "http://127.0.0.1:8001"


def _resolve_client_id(
    provided_id: Optional[int],
    state: Optional[ConversationState],
) -> Optional[int]:
    if provided_id is not None:
        try:
            return int(provided_id)
        except (TypeError, ValueError):
            return None
    if state:
        for key in ("client_id", "customerid", "customer_id"):
            stored = state.slots.get(key) or state.metadata.get(key)
            if stored is not None:
                try:
                    return int(stored)
                except (TypeError, ValueError):
                    continue
    return None


def get_client_accounts_info(
    *,
    client_id: Optional[int] = None,
    state: Optional[ConversationState] = None,
    language: Optional[str] = None,
) -> ToolExecutionResult:
    """
    Fetch client accounts to let the LLM choose an account for statements.
    """
    resolved_id = _resolve_client_id(client_id, state)
    if resolved_id is None:
        logger.warning("get_client_accounts_info() missing client_id")
        return ToolExecutionResult(
            event="send",
            data="Потрібен ідентифікатор клієнта, щоб отримати рахунки.",
            context_updates={},
            post_process=False,
        ) 

    try:
        params = {"clientid": resolved_id, "mode": 0}
        response = requests.get(
            # f"{BANK_API_BASE_URL}/api/chatbot/accounts",
            f"{CLIENT_SERVICE_BASE_URL}/accounts", 
            params=params,
            proxies={"http": None, "https": None},
            headers={"Content-Type": "application/json"},
            timeout=20,
        )
        logger.info("get_client_accounts_info() response", extra={"status": response.status_code})
        response.raise_for_status()
        payload = response.json()
        logger.info("get_client_accounts_info() payload", extra={"payload": payload})
    except requests.RequestException as exc:
        logger.warning("get_client_accounts_info() failed: %s", exc)
        return ToolExecutionResult(
            event="send",
            data="Cannot retrieve accounts right now.",
            context_updates={},
            post_process=False,
        )

    return ToolExecutionResult(
        event="send",
        data=payload,
        context_updates={"slots": {"accounts": payload, "client_id": resolved_id}},
        post_process=True,
    )

def get_statement(
    *,
    accountid: Optional[int],
    datefrom: Optional[str],
    dateinto: Optional[str],
    state: Optional[ConversationState],
    language: Optional[str],
) -> ToolExecutionResult:
    """
    Indicate that the chatbot backend should create for client bank statement for specific account with specific date range. 

    The legacy system already have all business logic for this, so AI agent must simply collect information for this function and emit it to chatbot backend.

    
    Docstring for get_statement
    
    :param accountid: Description
    :type accountid: Optional[int]
    :param datefrom: Description
    :type datefrom: Optional[datetime]
    :param dateinto: Description
    :type dateinto: Optional[datetime]
    :param state: Description
    :type state: Optional[ConversationState]
    :param language: Description
    :type language: Optional[str]
    :return: Description
    :rtype: ToolExecutionResult
    """

    logger.info("get_statement() tool usage")
    logger.info(
        f"get_statement() tool parameters: accountid={accountid}, datefrom= {datefrom}, dateinto= {dateinto}"
    )
    # logger.info(
    #     "get_statement() tool parameters",
    #     extra={"accountid": accountid, "datefrom": datefrom, "dateinto": dateinto},
    # )

    call = f"get_statement(accountid={accountid},datefrom={datefrom},dateinto={dateinto})"
    return ToolExecutionResult(
        event="function",
        data=call,
        context_updates={},
        post_process=False,
    )


STATEMENT_TOOLS: list[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_client_accounts_info",
            "description": (
                "Fetch all accounts for a client. Call this first if accountid is unknown when preparing a statement."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "integer",
                        "description": "Numeric client identifier in the bank system.",
                    }
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_statement",
            "description": (
                "Emit a function call instruction for the chatbot backend. If user asks about a bank statement/extract, use this tool. "
                "If accountid is unknown, first call get_client_accounts_info to retrieve accounts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "accountid": {
                        "type": "integer",
                        "description": (
                            "Client identifier inside bank system"
                        ),
                    },
                    "datefrom": {
                        "type": "string",
                        "format": "date-time",
                        "description": (
                            "Starting date/time for bank statement (ISO 8601 string, e.g. 2024-12-01 or 2024-12-01T00:00:00Z)"
                        ),
                    },
                    "dateinto": {
                        "type": "string",
                        "format": "date-time",
                        "description": (
                            "Ending date/time for bank statement (ISO 8601 string, e.g. 2024-12-31 or 2024-12-31T23:59:59Z)"
                        ),
                    },
                },
                "required": ["accountid", "datefrom", "dateinto"],
                "additionalProperties": False,
            },
        },
    },
]
