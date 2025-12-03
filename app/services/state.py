import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from app.schemas.inbound import ChatbotMessage
from app.schemas.state import ConversationState

# HISTORY_TTL = timedelta(hours=24)
HISTORY_TTL = timedelta(hours=2)


class ConversationStateStore:
    """
    Minimal async-safe in-memory state store.

    Replace with Redis or Postgres when moving to production.
    """

    def __init__(self) -> None:
        self._lock: Optional[asyncio.Lock] = None
        self._states: Dict[str, ConversationState] = {}

    def _ensure_lock(self) -> asyncio.Lock:
        """Create the asyncio lock inside an active event loop when first needed."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def load(self, payload: ChatbotMessage) -> ConversationState:
        """Fetch conversation state and hydrate with the latest chatbot context."""
        async with self._ensure_lock():
            state = self._states.get(payload.chat_id)
            now = datetime.now(timezone.utc)
            if state is None or (now - state.last_updated) > HISTORY_TTL:
                state = ConversationState(chat_id=payload.chat_id)
            state.merge_inbound_context(payload.context)
            state.touch()
            self._states[payload.chat_id] = state
            return state.clone()

    async def persist(self, state: ConversationState) -> None:
        """Persist the latest conversation snapshot."""
        async with self._ensure_lock():
            state.touch()
            self._states[state.chat_id] = state.clone()
