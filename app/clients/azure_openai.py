from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.config import settings

try:
    from openai import AsyncAzureOpenAI  # type: ignore
except Exception as import_error:  # pragma: no cover - optional dependency
    AsyncAzureOpenAI = None  # type: ignore
    _import_error = import_error
else:
    _import_error = None


class AzureOpenAIClient:
    """Thin wrapper around Azure OpenAI Chat Completions API."""

    def __init__(
        self,
        *,
        deployment: Optional[str] = None,
        temperature: float = 0.2,
        top_p: float = 0.9,
    ) -> None:
        if AsyncAzureOpenAI is None:
            raise RuntimeError(
                "The 'openai' package is required to use Azure OpenAI. "
                "Install it via 'pip install openai'."
            ) from _import_error

        if not settings.azure_openai_endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT is not configured.")
        if not settings.azure_openai_api_key:
            raise ValueError("AZURE_OPENAI_API_KEY is not configured.")

        self._deployment = deployment or settings.azure_openai_deployment
        if not self._deployment:
            raise ValueError("AZURE_OPENAI_DEPLOYMENT is not configured.")

        self._temperature = temperature
        self._top_p = top_p
        self._client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version="2024-02-15-preview",
            azure_endpoint=settings.azure_openai_endpoint,
        )

    async def generate(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> Any:
        """Invoke Azure OpenAI chat completions endpoint."""
        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=messages,
            temperature=self._temperature,
            top_p=self._top_p,
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=max_tokens,
        )
        return response

