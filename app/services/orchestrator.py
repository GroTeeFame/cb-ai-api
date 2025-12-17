import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from app.clients.azure_openai import AzureOpenAIClient
from app.schemas.inbound import ChatbotMessage
from app.schemas.responses import AgentReply
from app.schemas.state import ConversationState
from app.services.state import ConversationStateStore
from app.tools import (
    execute_tool,
    merge_context_updates,
    tool_schemas,
    UnknownToolError,
)
from app.tools.types import ToolExecutionResult

logger = logging.getLogger(__name__)

# SYSTEM_PROMPT = (
#     "You are a compliant digital banking assistant serving retail clients in Ukraine. "
#     "Respond only using Ukrainian language. "
#     "If the request requires back-end actions, decide whether to call an available tool. "
#     "Never invent account information. When unsure, ask follow-up questions. "
#     "If the user asks about bank branches, first ask which city they are looking for. "
#     "When tools are available, prefer calling them immediately over promising future actions. "
#     "For bank statements/extracts: if accountid is unknown, call get_client_accounts_info to fetch accounts, then choose the correct account (by currency/IBAN fragment) and call get_statement with accountid and date range in the SAME turn. Do not wait for extra user prompts if you already have the needed details."
# )

SYSTEM_PROMPT = (
    "You are a compliant digital banking assistant serving retail clients in Ukraine. "
    "Respond only using Ukrainian language. "
    "If the request requires back-end actions, decide whether to call an available tool. "
    "Never invent account information. When unsure, ask follow-up questions. "
    "If the user asks about bank branches, first ask which city they are looking for. "
    "If user ask same question/information about his bank account, and you already have it in history or memory, don't use those info, always use tools to get most recent information."
    "When tools are available, prefer calling them immediately over promising future actions. "
    "For bank statements/extracts: if accountid is unknown, call get_client_accounts_info to fetch accounts, then choose the correct account (by currency/IBAN fragment) and call get_statement with accountid and date range in the SAME turn. If you have all the info to use statement tool, prompt user with all the info to get permission to use tool. "
    "Do not use future dates for statements. If the user requests a future date range, ask them to provide a valid period up to today."
    "If the user only expresses thanks/acknowledgment without a new request, reply politely and do not call tools. "
)


class LLMOrchestrator:
    """Central coordinator that talks to Azure OpenAI and domain tools."""

    def __init__(
        self,
        *,
        llm_client_factory: Optional[Callable[[], AzureOpenAIClient]] = None,
        state_store: Optional[ConversationStateStore] = None,
        default_language: str = "uk",
    ) -> None:
        self._llm_client_factory = llm_client_factory
        self._llm_client: Optional[AzureOpenAIClient] = None
        self._state_store = state_store or ConversationStateStore()
        self._default_language = default_language
        self._max_history_messages = 20

    async def handle_turn(self, payload: ChatbotMessage) -> AgentReply:
        """Main entry point for a chatbot message."""
        state = await self._state_store.load(payload)

        logger.info(f"receive message from chatbot in turn endpoint")
        logger.info(f"chatbot message payload: {payload}")

        try:
            self._append_user_message(state, payload)
            completion = await self._invoke_llm(payload, state)
            agent_reply = await self._build_agent_reply(payload, completion, state)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.exception("LLM orchestration failed for chat_id=%s", payload.chat_id)
            agent_reply = self._fallback_reply(state, error=exc)

        if agent_reply.context_updates:
            state.apply_updates(agent_reply.context_updates)
        self._maybe_store_assistant_reply(agent_reply, state)
        await self._state_store.persist(state)
        return agent_reply

    async def answer_direct(
        self, *, question: str, language: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Lightweight entry point for direct question→answer flows without chatbot context.
        """
        language_code = language or self._default_language
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": question,
            },
        ]

        try:
            completion = await self._ensure_llm_client().generate(messages=messages)
            choice = self._safe_get_choice(completion)
            if not choice:
                raise ValueError("No choices returned from Azure OpenAI.")
            reply_text = self._extract_text(getattr(choice, "message", None) or {})
            if not reply_text:
                raise ValueError("Azure OpenAI returned an empty response.")
            return {
                "event": "send",
                "data": reply_text
            }
            # return {"answer": reply_text, "language": language_code}
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.exception("Direct answer LLM call failed.")
            fallback_state = ConversationState(chat_id="direct", language=language_code)
            fallback_reply = self._fallback_reply(fallback_state, error=exc)
            return {
                "event": fallback_reply.event,
                "data": fallback_reply.data,
            }
            # return {
            #     "answer": fallback_reply.reply_text or "",
            #     "language": fallback_reply.reply_language or language_code,
            # }

    async def _invoke_llm(
        self, payload: ChatbotMessage, state: ConversationState
    ) -> Any:
        client = self._ensure_llm_client()
        messages = self._build_messages(payload, state)
        tools = self._available_tools(state)
        return await client.generate(messages=messages, tools=tools)

    def _build_messages(
        self, payload: ChatbotMessage, state: ConversationState
    ) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(state.history)
        return messages

    def _available_tools(self, state: ConversationState) -> Optional[List[Dict[str, Any]]]:
        return tool_schemas()

    async def _build_agent_reply(
        self, payload: ChatbotMessage, completion: Any, state: ConversationState
    ) -> AgentReply:
        choice = self._safe_get_choice(completion)
        if not choice:
            return self._fallback_reply(state)

        message = getattr(choice, "message", None) or {}
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            return await self._handle_tool_calls(payload, tool_calls, state)

        reply_text = self._extract_text(message)
        if not reply_text:
            return self._fallback_reply(state)

        return AgentReply(
            event="send",
            data=reply_text or "",
            context_updates={},
        )
        # return AgentReply(
        #     reply_text=reply_text,
        #     reply_language=state.language or self._default_language,
        #     context_updates={},
        # )

    def _fallback_reply(
        self, state: ConversationState, error: Optional[Exception] = None
    ) -> AgentReply:
        language = state.language or self._default_language
        if language.startswith("en"):
            text = (
                "Sorry, I cannot process this request right now. "
                "Please try again in a moment."
            )
        else:
            text = (
                "Вибачте, наразі я не можу опрацювати запит. "
                "Будь ласка, спробуйте знову трохи пізніше."
            )

        updates: Dict[str, Any] = {}
        if error:
            logger.debug("Fallback reason: %s", error)
            updates = {"metadata": {"last_error": type(error).__name__}}
        return AgentReply(
            event="send",
            data=text,
            context_updates=updates,
        )
        # return AgentReply(
        #     reply_text=text,
        #     reply_language=language,
        #     context_updates=updates,
        # )

    async def _handle_tool_calls(
        self, payload: ChatbotMessage, tool_calls: Any, state: ConversationState
    ) -> AgentReply:
        language = state.language or self._default_language
        tool_results: List[ToolExecutionResult] = []
        tool_call_records: List[Any] = []
        updates_to_merge: List[Dict[str, Any]] = []

        for call in tool_calls:
            function = getattr(call, "function", None)
            name = getattr(function, "name", None) if function else None
            arguments = getattr(function, "arguments", "") if function else ""

            if not name:
                logger.warning("Received tool call without a function: %s", call)
                continue

            try:
                result = execute_tool(
                    name=name,
                    arguments=arguments,
                    state=state,
                    language=language,
                )
            except UnknownToolError as exc:
                logger.warning("Unknown tool requested: %s", exc)
                text = (
                    "The requested tool is unavailable right now."
                    if language.startswith("en")
                    else "Запитаний інструмент зараз недоступний."
                )
                return AgentReply(
                    event="send",
                    data=text,
                    context_updates={},
                )
                # return AgentReply(
                #     reply_text=text,
                #     reply_language=language,
                #     context_updates={},
                # )
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Tool '%s' execution failed.", name)
                return self._fallback_reply(state, error=exc)

            tool_results.append(result)
            tool_call_records.append(call)
            updates_to_merge.append(result.context_updates)
            if result.context_updates:
                state.apply_updates(result.context_updates)

        if not tool_results:
            return self._fallback_reply(state)

        context_updates = merge_context_updates(updates_to_merge)
        function_result = next(
            (res for res in tool_results if res.event != "send"),
            None,
        )
        if function_result:
            return AgentReply(
                event=function_result.event,
                data=function_result.data,
                context_updates=context_updates,
            )

        post_process_payloads: List[Dict[str, Any]] = []
        assistant_tool_calls: List[Dict[str, Any]] = []
        for idx, (call, result) in enumerate(zip(tool_call_records, tool_results)):
            if not result.post_process:
                continue
            call_id = self._tool_call_identifier(call, idx)
            assistant_tool_calls.append(self._build_assistant_tool_call(call, call_id))
            post_process_payloads.append(
                {
                    "tool_call_id": call_id,
                    "content": result.data or "",
                } 
            )

        if post_process_payloads:
            return await self._complete_with_tool_outputs(
                payload=payload,
                state=state,
                assistant_calls=assistant_tool_calls,
                tool_outputs=post_process_payloads,
                context_updates=context_updates,
            )

        reply_text = "\n\n".join(res.data for res in tool_results if res.data)
        return AgentReply(
            event="send",
            data=reply_text or "",
            context_updates=context_updates,
        )
        # return AgentReply(
        #     reply_text=reply_text or None,
        #     reply_language=language,
        #     context_updates=context_updates,
        # )

    def _ensure_llm_client(self) -> AzureOpenAIClient:
        if self._llm_client is None:
            if self._llm_client_factory is None:
                raise RuntimeError("No Azure OpenAI client factory configured.")
            self._llm_client = self._llm_client_factory()
        return self._llm_client

    async def _complete_with_tool_outputs(
        self,
        *,
        payload: ChatbotMessage,
        state: ConversationState,
        assistant_calls: List[Dict[str, Any]],
        tool_outputs: List[Dict[str, Any]],
        context_updates: Dict[str, Any],
    ) -> AgentReply:
        messages = self._build_messages(payload, state)
        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": assistant_calls,
            }
        )
        for output in tool_outputs:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": output["tool_call_id"],
                    "content": output["content"],
                }
            )

        try:
            completion = await self._ensure_llm_client().generate(messages=messages)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Post-tool LLM completion failed.")
            return self._fallback_reply(state, error=exc)

        choice = self._safe_get_choice(completion)
        if not choice:
            return self._fallback_reply(state)

        message = getattr(choice, "message", None) or {}
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            reply = await self._handle_tool_calls(payload, tool_calls, state)
            if context_updates and reply.context_updates:
                reply.context_updates = merge_context_updates(
                    [context_updates, reply.context_updates]
                )
            elif context_updates and not reply.context_updates:
                reply.context_updates = context_updates
            return reply

        reply_text = self._extract_text(message)
        if not reply_text:
            return self._fallback_reply(state)

        return AgentReply(
            event="send",
            data=reply_text,
            context_updates=context_updates,
        )

    @staticmethod
    def _tool_call_identifier(call: Any, idx: int) -> str:
        if hasattr(call, "id") and getattr(call, "id"):
            return getattr(call, "id")
        if isinstance(call, dict) and call.get("id"):
            return call["id"]
        return f"tool_call_{idx}"

    @staticmethod
    def _build_assistant_tool_call(call: Any, call_id: str) -> Dict[str, Any]:
        function = getattr(call, "function", None)
        if isinstance(call, dict):
            function = call.get("function", function)

        if isinstance(function, dict):
            name = function.get("name", "")
            arguments = function.get("arguments", "")
        else:
            name = getattr(function, "name", "") if function else ""
            arguments = getattr(function, "arguments", "") if function else ""

        if arguments is None:
            arguments = ""
        if not isinstance(arguments, str):
            try:
                arguments = json.dumps(arguments, ensure_ascii=False)
            except TypeError:
                arguments = str(arguments)

        return {
            "id": call_id,
            "type": "function",
            "function": {
                "name": name,
                "arguments": arguments or "{}",
            },
        }

    @staticmethod
    def _safe_get_choice(completion: Any) -> Optional[Any]:
        try:
            choices = getattr(completion, "choices", None)
            if not choices:
                return None
            return choices[0]
        except Exception:  # pragma: no cover - defensive
            return None

    @staticmethod
    def _extract_text(message: Any) -> str:
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            collected: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        collected.append(item.get("text", ""))
                elif isinstance(item, str):
                    collected.append(item)
            return "\n".join(part for part in collected if part).strip()

        return ""

    def _append_user_message(self, state: ConversationState, payload: ChatbotMessage) -> None:
        """Store the current user message in history."""
        language = state.language or payload.context.language or self._default_language
        state.append_history(
            "user",
            self._render_user_content(payload, state, language),
            max_messages=self._max_history_messages,
        )

    def _maybe_store_assistant_reply(self, reply: AgentReply, state: ConversationState) -> None:
        """Persist assistant reply into history if it's a textual send event."""
        if reply.event != "send" or not reply.data:
            return
        state.append_history(
            "assistant",
            str(reply.data),
            max_messages=self._max_history_messages,
        )

    @staticmethod
    def _render_user_content(
        payload: ChatbotMessage,
        state: ConversationState,
        language: str,
    ) -> str:
        """Render user input plus known context for the LLM."""
        tz_name = state.metadata.get("timezone") or payload.context.timezone
        now_iso, tz_used = LLMOrchestrator._current_timestamp(tz_name)
        user_payload = {
            "chat_id": payload.chat_id,
            "user_id": payload.user_id,
            "message_id": payload.message_id,
            "language": language,
            "slots": state.slots,
            "text": payload.text,
            "timestamp": {
                "iso": now_iso,
                "timezone": tz_used,
            },
        }

        return (
            "Below is the latest customer input and known context.\n"
            f"```json\n{json.dumps(user_payload, ensure_ascii=False, indent=2)}\n```"
        )

    @staticmethod
    def _current_timestamp(tz_name: Optional[str]) -> tuple[str, str]:
        """Return current timestamp and timezone used, defaulting to UTC."""
        tz = timezone.utc
        tz_used = "UTC"
        if tz_name:
            try:
                tz = ZoneInfo(tz_name)
                tz_used = tz.key if hasattr(tz, "key") else str(tz)
            except Exception:
                tz = timezone.utc
                tz_used = "UTC"
        now_iso = datetime.now(tz=tz).isoformat()
        return now_iso, tz_used
