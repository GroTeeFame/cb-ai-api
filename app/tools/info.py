from __future__ import annotations

from typing import Any, Dict, Optional

import requests
import logging

from app.schemas.state import ConversationState
from app.tools.types import ToolExecutionResult

from app.tools.bankinfo import BANK_INFO

logger = logging.getLogger(__name__)

def _language_bundle(language: Optional[str]) -> Dict[str, str]:
    if language and language.lower().startswith("en"):
        return {
            #TODO:
        }
    return {
        #TODO:
    }

#TODO: Here need to implement tool to extract info about bank, so agent can answer any bank questions without errors and halutinations 

def get_bank_info(
    *,
    topic,
    state: Optional[ConversationState],
    language: Optional[str],
) -> ToolExecutionResult:
    """
    Get info about bank, to give user answer with llm.

    Docstring for get_bank_info
    
    :param topic: Description
    :param state: Description
    :type state: Optional[ConversationState]
    :param language: Description
    :type language: Optional[str]
    :return: Description
    :rtype: ToolExecutionResult
    """

    entry = BANK_INFO.get(topic.lower())
    if not entry:
        return ToolExecutionResult(
            event="send",
            data="I don't have info on that topic.",
            context_updates={},
            post_process=False,
        )
    return ToolExecutionResult(
        event="send",
        data=f"{entry}",
        context_updates={},
        post_process=True,
    )
BANK_TOPICS = ["bank_branches",]
INFO_TOOLS: list[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_bank_info",
            "description": (
                "Return info about bank for specific topic"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": BANK_TOPICS,
                        "description": (
                            "Identifier of the information that needs to be obtained about the bank."
                        )
                    }
                },
                "required": ["topic"],
            },
        },
    },
]









#TODO: Ideas:
'''
Add bank facts to the system prompt: Extend SYSTEM_PROMPT in app/services/orchestrator.py with a concise, bullet-style fact sheet (e.g., brand name, hours, card limits, fees). Keep it short/stable so it doesn’t bloat tokens. Good for small, static info.
Serve a FAQ/tool for factual answers: Create a get_bank_info tool that returns curated answers keyed by topic (branches, hours, fees, card replacement). The LLM calls it when users ask bank questions, keeping answers grounded and updatable without model changes.
Embed and retrieve longer content: If you have policy docs or product pages, build a lightweight retrieval step (embeddings + vector store). On questions outside the FAQ, fetch top snippets and pass them to the LLM. This scales beyond the prompt without hallucinations.
Use guardrails for “no answer”: Add instructions to respond with “I don’t know” or escalate when info isn’t in the facts/FAQ/KB. This reduces hallucinations on regulated topics.
Version and scope the knowledge: Include an “as of” date and environment (prod/demo) in the prompt/tool outputs so the model doesn’t cite outdated numbers.
Instrument and iterate: Log bank-info questions, tool choices, and fallbacks; review them to expand the fact sheet/FAQ where users are asking.
Start small: add a short fact block to SYSTEM_PROMPT and a get_bank_info tool with curated answers. If coverage gaps remain, add retrieval for longer documents.
'''