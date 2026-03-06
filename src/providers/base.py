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
    def __init__(self, provider: str, message: str, *, status_code: int | None = None) -> None:
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"[{provider}] {message}")
