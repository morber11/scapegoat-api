from __future__ import annotations

import difflib
import logging

from core.constants.prompts import SYSTEM_PERSONALITY_PROMPT
from core.config import get_settings
from providers.base import AIProvider
from schemas.chat import ChatMessage, ChatRequest, ChatResponse

from services.token_utils import estimate_tokens, trim_messages

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_SIMILARITY_THRESHOLD = 0.75
_USER_ECHO_THRESHOLD = 0.7


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
        payload = list(history)
        settings = get_settings()
        budget = settings.max_input_tokens

        if estimate_tokens(SYSTEM_PERSONALITY_PROMPT, payload) > budget:
            trimmed = trim_messages(SYSTEM_PERSONALITY_PROMPT, payload, budget)
            logger.info(
                "trimming chat history from %d to %d messages to fit token budget",
                len(payload),
                len(trimmed),
            )
            payload = trimmed

        reply = await self._provider.generate_response(
            system_prompt=SYSTEM_PERSONALITY_PROMPT,
            messages=payload,
        )

        for _ in range(_MAX_RETRIES):
            reprompt = self._get_reprompt(reply, history)
            if reprompt is None:
                break

            logger.debug("response quality check failed - retrying: %s", reprompt)

            payload = payload + [ChatMessage(role="user", content=reprompt)]
            if estimate_tokens(SYSTEM_PERSONALITY_PROMPT, payload) > budget:
                trimmed = trim_messages(SYSTEM_PERSONALITY_PROMPT, payload, budget)
                logger.info(
                    "trimming chat history for retry from %d to %d messages",
                    len(payload),
                    len(trimmed),
                )
                payload = trimmed

            reply = await self._provider.generate_response(
                system_prompt=SYSTEM_PERSONALITY_PROMPT,
                messages=payload,
            )
        # instead of re prompting if there is a missing period, append it
        last_user_msg = history[-1].content if history and history[-1].role == "user" else ""
        if last_user_msg.endswith(".") and not reply.endswith("."):
            reply += "."

        return ChatResponse(
            messages=history + [ChatMessage(role="assistant", content=reply)]
        )


    def _get_reprompt(self, reply: str, messages: list[ChatMessage]) -> str | None:
        if not reply:
            return "please provide a response"

        reasons = []

        last_user = next((m.content for m in reversed(messages) if m.role == "user"), None)
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
                user_in_reply = sum(1 for w in user_words if w in reply_words) / len(user_words)
                reply_in_user = sum(1 for w in reply_words if w in set(user_words)) / len(reply_words)
                if min(user_in_reply, reply_in_user) >= _USER_ECHO_THRESHOLD:
                    reasons.append("your response is too similar to what the user just said - say something different")

        reply_lower = reply.lower()
        for m in messages:
            if m.role != "assistant" or not m.content:
                continue
            if difflib.SequenceMatcher(None, reply_lower, m.content.lower()).ratio() >= _SIMILARITY_THRESHOLD:
                reasons.append("vary your response - don't repeat something you've already said")
                break

        return ". ".join(reasons) + "." if reasons else None

