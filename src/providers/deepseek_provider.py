from __future__ import annotations

import logging
from typing import cast

import httpx

from core.config import ConfigNotSetError, Settings
from providers.base import ProviderError, ProviderName
from schemas.chat import ChatMessage

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider:

    def __init__(self, settings: Settings) -> None:
        if not settings.provider_api_key:
            raise ConfigNotSetError("PROVIDER_API_KEY")
        
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={"Authorization": f"Bearer {settings.provider_api_key}"},
            timeout=settings.request_timeout_seconds,
        )

    @property
    def provider_name(self) -> str:
        return ProviderName.DEEPSEEK

    @property
    def model_name(self) -> str:
        return self._settings.provider_model

    async def generate_response(self, system_prompt: str, messages: list[ChatMessage]) -> str:
        logger.info("sending request to deepseek model=%s", self._settings.provider_model)
        deepseek_messages = [
            {"role": "system", "content": system_prompt},
            *[
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ],
        ]

        try:
            resp = await self._client.post(
                "/chat/completions",
                json={
                    "model": self._settings.provider_model,
                    "messages": deepseek_messages,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            return cast(str, data["choices"][0]["message"]["content"])
        
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code

            if status == 429:
                raise ProviderError(ProviderName.DEEPSEEK, "rate limit exceeded", status_code=429) from exc
            
            body = exc.response.text[:500]
            
            raise ProviderError(ProviderName.DEEPSEEK, f"HTTP {status}: {body}", status_code=status) from exc
        except httpx.RequestError as exc:
            raise ProviderError(ProviderName.DEEPSEEK, str(exc)) from exc
        except ProviderError:
            raise
        except Exception as exc:
            # match GeminiProvider pattern - wrap unexpected errors
            raise ProviderError(ProviderName.DEEPSEEK, str(exc)) from exc
