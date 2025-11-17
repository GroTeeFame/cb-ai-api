from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ToolExecutionResult:
    """Normalized result produced by domain tools."""

    event: str = "send"
    data: str = ""
    context_updates: Dict[str, Any] = field(default_factory=dict)
    post_process: bool = False
