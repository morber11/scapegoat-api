from __future__ import annotations

import logging
from asyncio import to_thread

from google import genai
from google.genai import types

from core.config import Settings
from providers.base import ProviderError
from schemas.chat import ChatMessage

logger = logging.getLogger(__name__)

_PROVIDER_NAME = "gemini"


class GeminiProvider:

    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set."
                "copy .env.example to .env and fill in the value."
            )
        self._settings = settings
        self._client = genai.Client(api_key=settings.gemini_api_key)


    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    @property
    def model_name(self) -> str:
        return self._settings.gemini_model

    async def generate_response(self, system_prompt: str, messages: list[ChatMessage]) -> str:
        logger.info("sending request to gemini model=%s", self._settings.gemini_model)
        try:
            return await to_thread(self._call_gemini, system_prompt, messages)
        except ProviderError:
            raise
        except Exception as exc:
            status = None
            resp = getattr(exc, "response", None)
            if resp is not None and hasattr(resp, "status_code"):
                status = resp.status_code
            if status == 429:
                raise ProviderError(_PROVIDER_NAME, "rate limit exceeded", status_code=429) from exc
            # else just propagate the original message
            raise ProviderError(_PROVIDER_NAME, str(exc), status_code=status) from exc

    def _call_gemini(self, system_prompt: str, messages: list[ChatMessage]) -> str:
        contents = [
            types.Content(
                role="user" if msg.role == "user" else "model",
                parts=[types.Part.from_text(text=msg.content)],
            )
            for msg in messages
        ]

        logger.debug("gemini contents length=%d", len(contents))
        response = self._client.models.generate_content(
            model=self._settings.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
            ),
        )
        return response.text
