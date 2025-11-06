from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.config import settings

try:
    import httpx
except Exception as import_error:  # pragma: no cover - optional dependency
    httpx = None  # type: ignore
    _httpx_error = import_error
else:
    _httpx_error = None


class ChatbotAPIClient:
    """HTTP client used to call legacy chatbot endpoints."""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        timeout: float = 10.0,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        if httpx is None:
            raise RuntimeError(
                "The 'httpx' package is required for ChatbotAPIClient. "
                "Install it via 'pip install httpx'."
            ) from _httpx_error

        self._base_url = base_url or settings.chatbot_api_base_url
        if not self._base_url:
            raise ValueError("CHATBOT_API_BASE_URL is not configured.")

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout),
            headers=headers,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def post_event(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generic helper to post events to the chatbot API.

        Replace/extend with strongly typed methods when the API contract is available.
        """
        response = await self._client.post(endpoint, json=payload)
        response.raise_for_status()
        return response.json()

