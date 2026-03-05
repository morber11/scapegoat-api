from __future__ import annotations

from typing import Protocol, runtime_checkable

from schemas.chat import ChatMessage


@runtime_checkable
class AIProvider(Protocol):
    @property
    def provider_name(self) -> str:
        ...

    @property
    def model_name(self) -> str:
        ...

    async def generate_response(
        self, system_prompt: str, messages: list[ChatMessage]
    ) -> str:
        ...


class ProviderError(Exception):
    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {message}")
