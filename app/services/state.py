import asyncio
from typing import Dict

from app.schemas.inbound import ChatbotMessage
from app.schemas.state import ConversationState


class ConversationStateStore:
    """
    Minimal async-safe in-memory state store.

    Replace with Redis or Postgres when moving to production.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._states: Dict[str, ConversationState] = {}

    async def load(self, payload: ChatbotMessage) -> ConversationState:
        """Fetch conversation state and hydrate with the latest chatbot context."""
        async with self._lock:
            state = self._states.get(payload.chat_id)
            if state is None:
                state = ConversationState(chat_id=payload.chat_id)
            state.merge_inbound_context(payload.context)
            self._states[payload.chat_id] = state
            return state.clone()

    async def persist(self, state: ConversationState) -> None:
        """Persist the latest conversation snapshot."""
        async with self._lock:
            self._states[state.chat_id] = state.clone()

