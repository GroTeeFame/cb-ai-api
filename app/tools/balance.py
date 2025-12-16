from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
import json
import logging
import requests

from app.schemas.state import ConversationState
from app.tools.types import ToolExecutionResult

logger = logging.getLogger(__name__)

BANK_API_BASE_URL = "http://10.129.132.15:8000"

CLIENT_SERVICE_BASE_URL = "http://127.0.0.1:8001"
# CLIENT_SERVICE_BASE_URL = "http://127.0.0.1:8001"


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
        "not_found": "Рахунок {account} не знайдено.",
        "balance_template": "Баланс на рахунку {account}: {amount} {currency}",
    }


def _normalize_multi_value(
    value: Optional[Union[str, List[str]]],
    *,
    upper: bool = False,
) -> List[str]:
    """Normalize single or multiple string values into a list."""
    if value is None:
        return []
    values: List[str] = []
    items = value if isinstance(value, list) else [value]
    for item in items:
        if not isinstance(item, str):
            continue
        normalized = item.replace(" ", "")
        if upper:
            normalized = normalized.upper()
        if normalized:
            values.append(normalized)
    return values


def _resolve_accounts_by_fragment(*, client_id: int, fragment: str) -> List[str]:
    """Fetch accounts and return IBANs that match the fragment (prefix/suffix)."""
    logger.info(f"_resolve_accounts_by_fragment() usage with: fragment={fragment}")
    fragment_clean = fragment.replace(" ", "")
    if not fragment_clean:
        return []

    try:
        response = requests.get(
            f"{BANK_API_BASE_URL}/api/chatbot/accounts",
            # f"{CLIENT_SERVICE_BASE_URL}/accounts",
            params={"clientid": client_id, "mode": 0},
            proxies={"http": None, "https": None},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        logger.info(f"_resolve_accounts_by_fragment() answer from API: payload={payload}")

    except requests.RequestException as exc:
        logger.warning("Failed to resolve accounts for fragment '%s': %s", fragment, exc)
        return []

    matches: List[str] = []
    if isinstance(payload, list):
        for entry in payload:
            iban = str(entry.get("IBAN", "")).replace(" ", "")
            if not iban:
                continue
            if iban.endswith(fragment_clean) or iban.startswith(fragment_clean):
                matches.append(iban)
    
    logger.info(f"_resolve_accounts_by_fragment() return: matches={matches}")
    
    return matches


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
    logger.info("get_balance() tool usage")
    return ToolExecutionResult(
        event="function",
        data="get_balance",
        context_updates={},
        post_process=False,
    )

def get_specific_balance(
    *,
    client_id: Optional[int],
    mode: Optional[int] = 0,
    treatyid: Optional[int] = None,
    IBAN: Optional[Union[str, List[str]]] = None,
    currencyTag: Optional[Union[str, List[str]]] = None,
    account_fragment: Optional[str] = None,
    state: Optional[ConversationState],
    language: Optional[str],
) -> ToolExecutionResult:
    """
    Indicate that the chatbot backend should find and present client balance to client.

    The legacy system already holds every parameter, so the AI agent simply declares the intent.
    """
    logger.info("get_specific_balance() tool usage")
    logger.info(f"get_specific_balance() tool parameters: client_id={client_id}, mode={mode}, treatyid={treatyid}, IBAN={IBAN}, currencyTag={currencyTag}, account_fragment={account_fragment}")
    resolved_id = _resolve_client_id(client_id, state)
    if resolved_id is None:
        logger.warning("get_specific_balance() missing client_id/customerid") #FIXME: 
        resolved_id = 0  # explicit placeholder to avoid 'None'
    
    logger.info(f"get_specific_balance() inside balance.py, resolved_id = {resolved_id}") #TODO:

    mode_value = 0 if mode is None else mode
    iban_list = _normalize_multi_value(IBAN)
    short_fragments: List[str] = []
    if iban_list:
        # Treat very short entries as fragments rather than full IBANs.
        filtered_ibans: List[str] = []
        for item in iban_list:
            if len(item) < 12:
                short_fragments.append(item)
            else:
                filtered_ibans.append(item)
        iban_list = filtered_ibans
    currency_list = _normalize_multi_value(currencyTag, upper=True)

    # If we only have partial hints, try to resolve full IBANs via bank API.
    fragment_candidates: List[str] = []
    if account_fragment:
        fragment_candidates.append(account_fragment.replace(" ", ""))
    fragment_candidates.extend(short_fragments)

    if not iban_list and fragment_candidates:
        resolved_ibans: List[str] = []
        for frag in fragment_candidates:
            resolved_ibans.extend(
                _resolve_accounts_by_fragment(
                    client_id=resolved_id,
                    fragment=frag,
                )
            )
        if resolved_ibans:
            # Deduplicate while preserving order.
            seen = set()
            unique_ibans: List[str] = []
            for iban in resolved_ibans:
                if iban in seen:
                    continue
                seen.add(iban)
                unique_ibans.append(iban)
            iban_list = unique_ibans

    # Backend expects 'customerid' in the function string; keep schema using client_id for the LLM.
    line_to_return = (
        f"get_balance(customerid={resolved_id},mode={mode_value},"
        f"treatyid={treatyid},IBAN={json.dumps(iban_list, ensure_ascii=False)},"
        f"currencyTag={json.dumps(currency_list, ensure_ascii=False)})"
    )
    logger.info(f"get_specific_balance() tool return: {line_to_return}")
    return ToolExecutionResult(
        event="function",
        data=line_to_return,
        context_updates={},
        post_process=False,
    )


##TODO: WORKING tool, just dont needed right now ---<
# def get_specific_balance(
#     *,
#     client_id: Optional[int],
#     account: Optional[str] = None,
#     mode: Optional[int] = None,
#     state: Optional[ConversationState],
#     language: Optional[str],
# ) -> ToolExecutionResult:
#     """
#     Get list with all accounts and its balances, to give answer to user with LLM.
#     """
#     #TODO: Right now we search for IBAN with code, NOT by model reasoning. It works, but it will fail if user write IBAN with errors. We can give model opportunity to find needed IBAN by herself, for this we need to delete code part in this function for search of IBAN, and send full list of IBAN back to LLM for reasoning.
#     strings = _language_bundle(language)
#     if client_id is None:
#         logger.warning("get_specific_balance() missing client_id")
#         return ToolExecutionResult(
#             event='function',
#             data='get_balance',
#             context_updates={},
#             post_process=False,
#         )

#     account_normalized = account.replace(" ", "") if account else None
#     mode_value = 0 if mode is None else mode
#     logger.info(
#         "get_specific_balance() request",
#         extra={"client_id": client_id, "mode": mode_value, "account": account_normalized},
#     )

#     try:
#         params = {
#             "clientid": client_id,
#             "mode": mode_value,
#         }
#         logger.info("get_specific_balance() params", extra=params)
#         response = requests.get(
#             # f"{CLIENT_SERVICE_BASE_URL}/accounts", ##FIXME: for local dev testing
#             f"{BANK_API_BASE_URL}/api/chatbot/accounts", 
#             params=params,
#             proxies={"http": None, "https": None},
#             headers={"Content-Type": "application/json"},
#             timeout=20,
#         )

#         logger.info("get_specific_balance() response", extra={"status": response.status_code})
#         response.raise_for_status()
#         payload = response.json()
#         logger.info("get_specific_balance() payload", extra={"payload": payload})

#     except requests.RequestException as exc:
#         logger.warning("get_specific_balance() failed: %s", exc)
#         #TODO: here we can use two solution, we can send error to chatbot -> client.
#         #TODO: or we not send error, instead we send to chatbot command to execute this from its beckend
#         # return ToolExecutionResult(event='send', data=strings["error"])
        
#         return ToolExecutionResult(
#             event='function',
#             data='get_balance',
#             context_updates={},
#             post_process=False,
#         )
#     if not payload:
#         return ToolExecutionResult(
#             event='function',
#             data='get_balance',
#             context_updates={},
#             post_process=False,
#         )

#     if account_normalized:
#         # Find the specific account by IBAN/account number.
#         match = None
#         if isinstance(payload, list):
#             for entry in payload:
#                 entry_iban = str(entry.get("IBAN", "")).replace(" ", "")
#                 if entry_iban == account_normalized:
#                     match = entry
#                     break
#         if match:
#             amount = match.get("amountRest", "")
#             currency = match.get("currencyTag", "")
#             message = strings["balance_template"].format(
#                 account=account_normalized,
#                 amount=amount,
#                 currency=currency,
#             )
#             return ToolExecutionResult(
#                 event='send',
#                 data=message,
#                 context_updates={},
#                 post_process=False,
#             )
#         return ToolExecutionResult(
#             event='send',
#             data=strings["not_found"].format(account=account_normalized),
#             context_updates={},
#             post_process=False,
#         )

#     return ToolExecutionResult(
#         event='send',
#         data=payload,
#         context_updates={},
#         post_process=True,
#     )
##TODO: WORKING tool, just dont needed right now --->

CURRENCY_LIST = ["UAH", "USD", "EUR"]

BALANCE_TOOLS: list[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_balance",
            "description": (
                "Request the legacy chatbot backend to find and send current account balance to client. If user ask about balances, or want to get all balances, use this tool."
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
                "Emit a function call instruction for the chatbot backend. If user ask about specific balance, or want to get balance, use this tool."
                # "Request the legacy chatbot backend to find and send specific account balance to client. If user ask about specific balance, or want to get balance, use this tool."
                # "Request the list with all user accounts and balances to give user answers about specific account and balance. with LLM processing. Use this tool if user ask you about specific balance or specific currency of balance, or mentioned IBAN."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "integer",
                        "description": (
                            "Identifier of the client in bank database"
                        ),
                    },
                    "mode": {
                        "type": "integer",
                        "description": (
                            "Identifier of kind of search for account/balance search."
                        )
                    },
                    "treatyid": {
                        "type": "integer",
                        "description": (
                            "Contract identifier, in this case its always must be empty."
                        ),
                    },
                    "IBAN": {
                        "oneOf": [
                            {"type": "string"},
                            {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        ],
                        "description": (
                            "Account number or IBAN the user is asking about (string or array of strings)."
                        ),
                    },
                    "currencyTag": {
                        "oneOf": [
                            {"type": "string", "enum": CURRENCY_LIST},
                            {
                                "type": "array",
                                "items": {"type": "string", "enum": CURRENCY_LIST},
                            },
                        ],
                        "description": (
                            "Currency identifier(s) the user is asking about (string or array)."
                        ),
                    },
                },
                "required": ["client_id"],
                "additionalProperties": False,
            },
        },
    },
##TODO: WORKING tool, just dont needed right now ---<
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "get_specific_balance",
    #         "description": (
    #             "Request the list with all user accounts and balances to give user answers about specific account and balance. with LLM processing. Use this tool if user ask you about specific balance or specific currency of balance, or mentioned IBAN."
    #         ),
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "client_id": {
    #                     "type": "integer",
    #                     "description": (
    #                         "Identifier of the client in bank database"
    #                     ),
    #                 },
    #                 "account": {
    #                     "type": "string",
    #                     "description": (
    #                         "Account number or IBAN the user is asking about."
    #                     ),
    #                 },
    #                 "mode": {
    #                     "type": "integer",
    #                     "description": (
    #                         "Identifier of kind of search for account/balance search."
    #                     )
    #                 }
    #             },
    #             "required": ["client_id"],
    #             "additionalProperties": False,
    #         },
    #     },
    # },
##TODO: WORKING tool, just dont needed right now --->

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
