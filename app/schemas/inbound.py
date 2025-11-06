from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatContext(BaseModel):
    """Conversation state snapshot provided by the chatbot (if any)."""

    language: Optional[str] = Field(
        default='uk',
        description="IETF language tag preferred by the user (e.g. 'uk', 'en').",
    )
    timezone: Optional[str] = Field(
        default=None, description="End-user timezone identifier if known."
    )
    slots: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary slot values already collected for the user.",
    )


class ChatbotMessage(BaseModel):
    """Inbound payload posted by the legacy chatbot backend."""

    chat_id: str = Field(description="Unique identifier of the chat/dialogue.")
    user_id: Optional[str] = Field(
        default=None, description="Optional unique user identifier."
    )
    message_id: Optional[str] = Field(
        default=None, description="Identifier of the message within the chatbot system."
    )
    text: str = Field(description="Raw text provided by the end-user.")
    is_private: bool = Field(
        default=True,
        description="Flag indicating whether the conversation channel is private.",
    )
    context: ChatContext = Field(
        default_factory=ChatContext,
        description="Conversation context captured by the chatbot.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Transport metadata, user agent, experiments, etc.",
    )

