from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentDirective(BaseModel):
    """Instruction for the legacy chatbot about what to do next."""

    type: str = Field(description="Directive type, e.g. 'reply', 'handoff', 'error'.")
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Payload understood by the chatbot."
    )


class AgentReply(BaseModel):
    """Structured response returned to the chatbot."""
    
    event: str = Field(
        default="send",
        description="Event for chatbot backend to perform.",
    )
    data: str = Field(
        default="",
        description="Additional data for the event (text, function name, etc.).",
    )
    context_updates: Dict[str, Any] = Field(
        default_factory=dict,
        description="Updates that should be merged into stored chat state.",
        exclude=True,
    )



# class AgentReply(BaseModel):
#     """Structured response returned to the chatbot."""

#     reply_text: Optional[str] = Field(
#         default=None, description="Natural language reply for the end-user."
#     )
#     reply_language: Optional[str] = Field(
#         default=None,
#         description="IETF language tag for the reply (chatbot can translate if needed).",
#     )
#     directives: List[AgentDirective] = Field(
#         default_factory=list,
#         description="Optional list of directives for the chatbot to execute.",
#     )
#     context_updates: Dict[str, Any] = Field(
#         default_factory=dict,
#         description="Updates that should be merged into stored chat state.",
#     )
