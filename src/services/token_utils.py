from __future__ import annotations

from collections.abc import Iterable

from schemas.chat import ChatMessage

_DEFAULT_TOKEN_DIVISOR = 4


def estimate_tokens(system_prompt: str, messages: Iterable[ChatMessage]) -> int:
    total = len(system_prompt)
    for msg in messages:
        total += len(msg.content)
    return total // _DEFAULT_TOKEN_DIVISOR


def trim_messages(
    system_prompt: str, messages: list[ChatMessage], limit: int
) -> list[ChatMessage]:
    if estimate_tokens(system_prompt, messages) <= limit:
        return list(messages)
    
    trimmed = list(messages)
    while trimmed and estimate_tokens(system_prompt, trimmed) > limit:
        trimmed.pop(0)
        
    return trimmed
