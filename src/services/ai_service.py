from __future__ import annotations

import asyncio
import difflib
import logging

from core.config import get_settings
from core.constants.prompts import SYSTEM_PERSONALITY_PROMPT
from providers.base import AIProvider, ProviderError
from schemas.chat import ChatMessage, ChatRequest, ChatResponse, MessageRole
from services.token_utils import estimate_tokens, trim_messages

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_DELAYS = (3, 5, 10)
_QUALITY_RETRY_DELAYS = (1, 1, 1)
_SIMILARITY_THRESHOLD = 0.75
_USER_ECHO_THRESHOLD = 0.7
_MAX_REPLY_CHECK = 5  # only compare against the last N assistant turns to keep difflib fast on long histories
_EMPTY_REPLY_PLACEHOLDER = "(no response generated)"


class AIService:
    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    async def chat(self, request: ChatRequest) -> ChatResponse:
        logger.info(
            "chat request received from provider=%s model=%s",
            self._provider.provider_name,
            self._provider.model_name,
        )

        history = list(request.messages)
        settings = get_settings()
        budget = settings.max_input_tokens

        payload = self._trim_to_budget(history, budget)
        reply = await self._attempt_with_retry(payload, history, budget)

        # instead of re prompting if there is a missing period, append it
        last_user_msg = history[-1].content if history and history[-1].role == MessageRole.USER else ""
        if last_user_msg.endswith(".") and not reply.endswith("."):
            reply += "."

        return ChatResponse(
            messages=history + [ChatMessage(role=MessageRole.ASSISTANT, content=reply)]
        )


    def _trim_to_budget(
        self, messages: list[ChatMessage], budget: int
    ) -> list[ChatMessage]:
        if estimate_tokens(SYSTEM_PERSONALITY_PROMPT, messages) > budget:
            trimmed = trim_messages(SYSTEM_PERSONALITY_PROMPT, messages, budget)
            logger.info(
                "trimming chat history from %d to %d messages to fit token budget",
                len(messages),
                len(trimmed),
            )
            return trimmed
        return list(messages)


    async def _attempt_with_retry(
        self, payload: list[ChatMessage], history: list[ChatMessage], budget: int
    ) -> str:
        last_index = _MAX_RETRIES - 1
        for attempt in range(_MAX_RETRIES):
            try:
                reply = await self._provider.generate_response(
                    system_prompt=SYSTEM_PERSONALITY_PROMPT,
                    messages=payload,
                )
            except ProviderError:
                if attempt < last_index:
                    await asyncio.sleep(self._delay_for(attempt, _RETRY_DELAYS))
                    continue
                raise

            reprompt = self._get_reprompt(reply, history)

            if reprompt is None or attempt == last_index:
                break

            logger.debug("response quality check failed - retrying: %s", reprompt)

            assistant_turn_content = reply if reply else _EMPTY_REPLY_PLACEHOLDER
            payload = payload + [
                ChatMessage(role=MessageRole.ASSISTANT, content=assistant_turn_content),
                ChatMessage(role=MessageRole.USER, content=self._wrap_reprompt(reprompt)),
            ]
            
            payload = self._trim_to_budget(payload, budget)

            await asyncio.sleep(self._delay_for(attempt, _QUALITY_RETRY_DELAYS))

        return reply


    @staticmethod
    def _delay_for(attempt: int, delays: tuple[int, ...]) -> int:
        return delays[min(attempt, len(delays) - 1)]


    def _wrap_reprompt(self, reprompt: str) -> str:
        return (
            "[Automated quality check on your previous reply - this is not "
            f"from the user] {reprompt} Please revise your last response accordingly"
        )


    def _get_reprompt(self, reply: str, messages: list[ChatMessage]) -> str | None:
        if not reply:
            return "please provide a response"

        reasons = []

        last_user = next((m.content for m in reversed(messages) if m.role == MessageRole.USER), None)
        if last_user and last_user[0].isalpha():
            user_is_lowercase = last_user == last_user.lower()
            reply_starts_upper = reply[0].isalpha() and reply[0].isupper()
            if user_is_lowercase and reply_starts_upper:
                reasons.append("the user types in lowercase - match their style, do not capitalise your response")
            elif not user_is_lowercase and reply[0].isalpha() and reply[0].islower():
                reasons.append("the user types with proper capitalisation - start your response with a capital letter")


        if last_user and last_user.lower() != reply.lower():
            user_words = [w.strip(".,!?;:'\"") for w in last_user.lower().split()]
            reply_words = {w.strip(".,!?;:'\"") for w in reply.lower().split()}
            if user_words and reply_words:
                user_words_set = set(user_words)
                user_in_reply = sum(1 for w in user_words if w in reply_words) / len(user_words)
                reply_in_user = sum(1 for w in reply_words if w in user_words_set) / len(reply_words)
                if min(user_in_reply, reply_in_user) >= _USER_ECHO_THRESHOLD:
                    reasons.append("your response is too similar to what the user just said - say something different")

        reply_lower = reply.lower()
        checked = 0
        for m in reversed(messages):
            if m.role != MessageRole.ASSISTANT or not m.content:
                continue
            if checked >= _MAX_REPLY_CHECK:
                break
            checked += 1
            if difflib.SequenceMatcher(None, reply_lower, m.content.lower()).ratio() >= _SIMILARITY_THRESHOLD:
                reasons.append("vary your response - don't repeat something you've already said")
                break

        return ". ".join(reasons) + "." if reasons else None

