from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Dict, List, Optional

from app.core.config import settings

try:
    from openai import AsyncAzureOpenAI  # type: ignore
except Exception as import_error:  # pragma: no cover - optional dependency
    AsyncAzureOpenAI = None  # type: ignore
    _import_error = import_error
else:
    _import_error = None


logger = logging.getLogger(__name__)


class AzureOpenAIClient:
    """Thin wrapper around Azure OpenAI Chat Completions API."""

    def __init__(
        self,
        *,
        deployment: Optional[str] = None,
        temperature: float = 0.2,
        top_p: float = 0.9,
        max_retries: Optional[int] = None,
        retry_base_delay: Optional[float] = None,
        retry_max_delay: Optional[float] = None,
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
        self._max_retries = (
            max_retries
            if max_retries is not None
            else max(0, settings.azure_openai_max_retries)
        )
        self._retry_base_delay = (
            retry_base_delay
            if retry_base_delay is not None
            else max(0.0, settings.azure_openai_retry_base_delay)
        )
        self._retry_max_delay = (
            retry_max_delay
            if retry_max_delay is not None
            else max(0.0, settings.azure_openai_retry_max_delay)
        )
        if self._retry_max_delay and self._retry_base_delay > self._retry_max_delay:
            self._retry_max_delay = self._retry_base_delay

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
        """Invoke Azure OpenAI chat completions endpoint with retry logic."""
        attempt = 0
        while True:
            try:
                return await self._client.chat.completions.create(
                    model=self._deployment,
                    messages=messages,
                    temperature=self._temperature,
                    top_p=self._top_p,
                    tools=tools,
                    tool_choice=tool_choice,
                    max_tokens=max_tokens,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if attempt >= self._max_retries:
                    logger.error(
                        "Azure OpenAI request failed after %s attempts",
                        attempt + 1,
                        exc_info=exc,
                    )
                    raise
                attempt += 1
                delay = self._compute_backoff(attempt)
                logger.warning(
                    "Azure OpenAI request failed (attempt %s/%s). Retrying in %.2fs",
                    attempt,
                    self._max_retries,
                    delay,
                    exc_info=exc,
                )
                await asyncio.sleep(delay)

    def _compute_backoff(self, attempt: int) -> float:
        base = self._retry_base_delay or 0.0
        if base <= 0:
            return 0.0
        delay = base * (2 ** (attempt - 1))
        if self._retry_max_delay:
            delay = min(delay, self._retry_max_delay)
        jitter = random.uniform(0.8, 1.2)
        return max(0.0, delay * jitter)
