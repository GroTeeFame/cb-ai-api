from functools import lru_cache

from app.clients.azure_openai import AzureOpenAIClient
from app.services.orchestrator import LLMOrchestrator
from app.services.state import ConversationStateStore


@lru_cache()
def get_state_store() -> ConversationStateStore:
    """Provide a shared conversation state store instance."""
    return ConversationStateStore()


def build_llm_client() -> AzureOpenAIClient:
    """Factory for the Azure OpenAI client."""
    return AzureOpenAIClient()


@lru_cache()
def get_orchestrator() -> LLMOrchestrator:
    """Provide a shared orchestrator wired with dependencies."""
    return LLMOrchestrator(
        llm_client_factory=build_llm_client,
        state_store=get_state_store(),
    )
