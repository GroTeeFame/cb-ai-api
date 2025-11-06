from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import requests

from app.schemas.state import ConversationState

# Base URL for the customer data service. In production, move this into config.
CLIENT_SERVICE_BASE_URL = "http://127.0.0.1:8001"


class ClientNotFoundError(Exception):
    """Raised when a client ID cannot be located in the dataset."""


def _resolve_client_id(
    provided_id: Optional[int],
    state: Optional[ConversationState],
) -> Optional[int]:
    """Return client id from tool arguments or stored conversation slots."""
    if provided_id is not None:
        return int(provided_id)

    if state:
        stored = state.slots.get("client_id")
        if stored is not None:
            try:
                return int(stored)
            except (TypeError, ValueError):
                return None
    return None


def _fetch_client_profile(client_id: int) -> Dict[str, Any]:
    """Fetch a single client profile from the customer service."""
    try:
        response = requests.get(
            f"{CLIENT_SERVICE_BASE_URL}/find_client_by_id",
            params={"client_id": client_id},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Customer service lookup failed: {exc}") from exc

    if response.status_code == 404:
        raise ClientNotFoundError(f"Client with id={client_id} not found.")

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(
            f"Customer service returned an error ({response.status_code})."
        ) from exc

    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Customer service returned an unexpected payload.")
    return payload


def _language_bundle(language: Optional[str]) -> Dict[str, str]:
    """Provide localized snippets used in tool replies."""
    if language and language.lower().startswith("en"):
        return {
            "missing_id": (
                "I need a client ID to continue. "
                "Please provide the identifier shown in the test dataset."
            ),
            "not_found": "I could not find a client with ID {client_id}.",
            "balances_heading": "Balances for client #{client_id}{full_name}:",
            "empty_accounts": "There are no accounts for client #{client_id}.",
            "total_balance": (
                "Total balance for client #{client_id}{full_name} "
                "is {amount} across {count} account(s)."
            ),
            "error_generic": (
                "I cannot retrieve the account information right now. "
                "Please try again in a moment."
            ),
        }

    return {
        "missing_id": (
            "Потрібен ідентифікатор клієнта, щоб продовжити. "
            "Будь ласка, вкажіть номер зі списку тестових клієнтів."
        ),
        "not_found": "Не вдалося знайти клієнта з ID {client_id}.",
        "balances_heading": "Баланси для клієнта №{client_id}{full_name}:",
        "empty_accounts": "Для клієнта №{client_id} відсутні рахунки.",
        "total_balance": (
            "Сумарний баланс для клієнта №{client_id}{full_name} "
            "становить {amount} на {count} рахунках."
        ),
        "error_generic": (
            "Не вдається отримати інформацію про рахунки. "
            "Будь ласка, спробуйте трохи пізніше."
        ),
    }


# def lookup_client_balances(
#     *,
#     client_id: Optional[int],
#     state: Optional[ConversationState],
#     language: Optional[str],
# ) -> Tuple[str, Dict[str, Any]]:
#     """
#     Return formatted balances for every account owned by the client.

#     Returns a tuple of human-friendly reply text and optional context updates.
#     """
#     strings = _language_bundle(language)
#     resolved_id = _resolve_client_id(client_id, state)
#     if resolved_id is None:
#         return strings["missing_id"], {}

#     try:
#         client = _fetch_client_profile(resolved_id)
#     except ClientNotFoundError:
#         return strings["not_found"].format(client_id=resolved_id), {}
#     except Exception:
#         return strings["error_generic"], {}

#     accounts: List[Dict[str, Any]] = client.get("accounts", [])
#     name_parts = [
#         client.get("name", "").strip(),
#         client.get("surname", "").strip(),
#     ]
#     full_name_suffix = ""
#     name = " ".join(part for part in name_parts if part)
#     if name:
#         full_name_suffix = f" ({name})"

#     if not accounts:
#         text = strings["empty_accounts"].format(client_id=resolved_id)
#     else:
#         lines = [
#             strings["balances_heading"].format(
#                 client_id=resolved_id, full_name=full_name_suffix
#             )
#         ]
#         for account in accounts:
#             currency = str(account.get("currency", "")).upper()
#             balance = account.get("balance", 0)
#             lines.append(f"- {currency}: {balance}")
#         text = "\n".join(lines)

#     updates = {"slots": {"client_id": resolved_id}}
#     return text, updates

# client_balances

def lookup_client_balances(
    *,
    client_id: Optional[int],
    state: Optional[ConversationState],
    language: Optional[str],
) -> Tuple[str, Dict[str, Any]]:
    """
    Return formatted balances for every account owned by the client.

    Returns a tuple of human-friendly reply text and optional context updates.
    """
    strings = _language_bundle(language)
    resolved_id = _resolve_client_id(client_id, state)
    if resolved_id is None:
        return strings["missing_id"], {}

    try:
        client = _fetch_client_profile(resolved_id)
    except ClientNotFoundError:
        return strings["not_found"].format(client_id=resolved_id), {}
    except Exception:
        return strings["error_generic"], {}

    accounts: List[Dict[str, Any]] = client.get("accounts", [])

    accounts: Optional[float] = None
    try:
        response = requests.get(
            f"{CLIENT_SERVICE_BASE_URL}/client_balances",
            params={"client_id": resolved_id},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        if response.status_code == 200:
            payload = response.json()
            if isinstance(payload, dict):
                accounts = payload.get("accounts")
            else:
                accounts = payload
        else:
            response.raise_for_status()
    except requests.RequestException:
        accounts = None

    if accounts is None:
        return strings["error_generic"], {}


    name_parts = [
        client.get("name", "").strip(),
        client.get("surname", "").strip(),
    ]
    full_name_suffix = ""
    name = " ".join(part for part in name_parts if part)
    if name:
        full_name_suffix = f" ({name})"

    if not accounts:
        text = strings["empty_accounts"].format(client_id=resolved_id)
    else:
        lines = [
            strings["balances_heading"].format(
                client_id=resolved_id, full_name=full_name_suffix
            )
        ]
        for account in accounts:
            currency = str(account.get("currency", "")).upper()
            balance = account.get("balance", 0)
            lines.append(f"- {currency}: {balance}")
        text = "\n".join(lines)

    updates = {"slots": {"client_id": resolved_id}}
    return text, updates


def lookup_total_balance(
    *,
    client_id: Optional[int],
    state: Optional[ConversationState],
    language: Optional[str],
) -> Tuple[str, Dict[str, Any]]:
    """
    Return a formatted message describing the aggregated client balance.
    """
    strings = _language_bundle(language)
    resolved_id = _resolve_client_id(client_id, state)
    if resolved_id is None:
        return strings["missing_id"], {}

    try:
        client = _fetch_client_profile(resolved_id)
    except ClientNotFoundError:
        return strings["not_found"].format(client_id=resolved_id), {}
    except Exception:
        return strings["error_generic"], {}

    full_name_suffix = ""
    name_parts = [
        client.get("name", "").strip(),
        client.get("surname", "").strip(),
    ]
    name = " ".join(part for part in name_parts if part)
    if name:
        full_name_suffix = f" ({name})"

    accounts: List[Dict[str, Any]] = client.get("accounts", [])
    account_count = len(accounts)

    total: Optional[float] = None
    try:
        response = requests.get(
            f"{CLIENT_SERVICE_BASE_URL}/client_total_balance",
            params={"client_id": resolved_id},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        if response.status_code == 200:
            payload = response.json()
            if isinstance(payload, dict):
                total = payload.get("total_balance")
            else:
                total = payload
        else:
            response.raise_for_status()
    except requests.RequestException:
        total = None

    if total is None:
        return strings["error_generic"], {}

    text = strings["total_balance"].format(
        client_id=resolved_id,
        full_name=full_name_suffix,
        amount=total,
        count=account_count,
    )
    updates = {"slots": {"client_id": resolved_id}}
    return text, updates


BALANCE_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_client_balances",
            "description": (
                "Look up account balances for a banking client in the demo dataset. "
                "Provide the numeric client_id if known; otherwise the value stored "
                "in conversation context will be used."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "integer",
                        "description": (
                            "Identifier of the client in the test dataset. "
                            "If omitted, the assistant will use the stored client_id slot."
                        ),
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
            "name": "lookup_total_balance",
            "description": (
                "Summarize the total balance across all accounts for a client "
                "in the demo banking dataset."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "integer",
                        "description": (
                            "Identifier of the client in the test dataset. "
                            "If omitted, the assistant will use the stored client_id slot."
                        ),
                    }
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]
