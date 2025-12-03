from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.schemas.inbound import ChatContext


class ConversationState(BaseModel):
    """Aggregated view of what we know about a chat session."""

    chat_id: str
    language: Optional[str] = None
    slots: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    history: List[Dict[str, str]] = Field(default_factory=list)
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def merge_inbound_context(self, context: ChatContext) -> None:
        """Update state from context provided by the legacy chatbot."""
        if context.language and not self.language:
            self.language = context.language
        if context.slots:
            self.slots.update(context.slots)
        if context.timezone:
            self.metadata.setdefault("timezone", context.timezone)

    def apply_updates(self, updates: Dict[str, Any]) -> None:
        """Apply changes requested by the orchestrator."""
        if not updates:
            return

        language = updates.get("language")
        if language:
            self.language = language

        slots = updates.get("slots")
        if isinstance(slots, dict):
            self.slots.update(slots)

        metadata = updates.get("metadata")
        if isinstance(metadata, dict):
            self.metadata.update(metadata)

        # Persist any additional free-form keys under metadata to avoid loss.
        for key, value in updates.items():
            if key not in {"language", "slots", "metadata"}:
                self.metadata[key] = value

    def clone(self) -> "ConversationState":
        """Return a deep copy of the current state instance."""
        copy_method = getattr(self, "model_copy", None)
        if callable(copy_method):
            return copy_method(deep=True)
        return self.copy(deep=True)  # type: ignore[return-value, call-arg]

    def touch(self) -> None:
        """Refresh last_updated timestamp."""
        self.last_updated = datetime.now(timezone.utc)

    def append_history(
        self, role: str, content: str, *, max_messages: int = 20
    ) -> None:
        """Append a message to the conversation history with trimming."""
        if not content:
            return
        self.history.append({"role": role, "content": content})
        if max_messages > 0 and len(self.history) > max_messages:
            self.history = self.history[-max_messages:]
        self.touch()
