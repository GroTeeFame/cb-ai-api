from typing import Optional

from app.clients.azure_openai import AzureOpenAIClient
from app.services.orchestrator import LLMOrchestrator
from app.services.state import ConversationStateStore


_state_store: Optional[ConversationStateStore] = None
_orchestrator: Optional[LLMOrchestrator] = None


async def get_state_store() -> ConversationStateStore:
    """Provide a shared conversation state store instance."""
    global _state_store
    if _state_store is None:
        _state_store = ConversationStateStore()
    return _state_store


def build_llm_client() -> AzureOpenAIClient:
    """Factory for the Azure OpenAI client."""
    return AzureOpenAIClient()


async def get_orchestrator() -> LLMOrchestrator:
    """Provide a shared orchestrator wired with dependencies."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = LLMOrchestrator(
            llm_client_factory=build_llm_client,
            state_store=await get_state_store(),
        )
    return _orchestrator
