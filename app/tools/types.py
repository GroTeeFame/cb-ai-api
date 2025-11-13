from __future__ import annotations

from typing import Any, Dict, NamedTuple


class ToolExecutionResult(NamedTuple):
    """Normalized result produced by domain tools."""

    event: str
    data: str
    context_updates: Dict[str, Any]
