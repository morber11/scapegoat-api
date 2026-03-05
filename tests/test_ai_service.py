from unittest.mock import AsyncMock, MagicMock

import pytest

from core.constants.prompts import SYSTEM_PERSONALITY_PROMPT
from providers.base import ProviderError
from schemas.chat import ChatMessage, ChatRequest
from services.ai_service import AIService


def _make_provider(reply: str = "hello") -> MagicMock:
    provider = MagicMock()
    provider.provider_name = "mock"
    provider.model_name = "mock-model"
    provider.generate_response = AsyncMock(return_value=reply)
    return provider


@pytest.mark.asyncio
async def test_chat_injects_personality_prompt() -> None:
    provider = _make_provider("I am Scapegoat?")
    service = AIService(provider)

    msg = ChatMessage(role="user", content="Who are you?")
    await service.chat(ChatRequest(messages=[msg]))

    assert provider.generate_response.await_count >= 1
    first_kwargs = provider.generate_response.await_args_list[0][1]
    assert first_kwargs["system_prompt"] == SYSTEM_PERSONALITY_PROMPT
    assert first_kwargs["messages"] == [msg]


@pytest.mark.asyncio
async def test_chat_returns_shaped_response() -> None:
    provider = _make_provider("42")
    service = AIService(provider)

    msg = ChatMessage(role="user", content="Answer")
    result = await service.chat(ChatRequest(messages=[msg]))

    assert len(result.messages) == 2
    assert result.messages[1].content == "42"


@pytest.mark.asyncio
async def test_provider_error_propagates() -> None:
    provider = _make_provider()
    provider.generate_response = AsyncMock(
        side_effect=ProviderError("mock", "rate limit exceeded")
    )
    service = AIService(provider)

    msg = ChatMessage(role="user", content="hello")
    with pytest.raises(ProviderError, match="rate limit exceeded"):
        await service.chat(ChatRequest(messages=[msg]))


@pytest.mark.asyncio
async def test_retry_on_similarity() -> None:
    user1 = ChatMessage(role="user", content="hey")
    assistant1 = ChatMessage(role="assistant", content="foo")
    user2 = ChatMessage(role="user", content="please respond")

    provider = _make_provider()
    provider.generate_response = AsyncMock(side_effect=["foo", "bar"])
    service = AIService(provider)

    result = await service.chat(ChatRequest(messages=[user1, assistant1, user2]))

    assert provider.generate_response.await_count == 2
    args = provider.generate_response.await_args_list[1][1]
    assert args["messages"][-1].role == "user"
    assert result.messages[-1].content == "bar"


@pytest.mark.asyncio
async def test_retry_on_grammar_mismatch() -> None:
    user = ChatMessage(role="user", content="Hello there.")
    provider = _make_provider()
    provider.generate_response = AsyncMock(side_effect=["hi", "Hi there."])
    service = AIService(provider)

    result = await service.chat(ChatRequest(messages=[user]))
    assert provider.generate_response.await_count == 2
    assert result.messages[-1].content == "Hi there."


@pytest.mark.asyncio
async def test_no_retry_if_response_ok() -> None:
    user = ChatMessage(role="user", content="Hi!")
    provider = _make_provider("Hi!")
    service = AIService(provider)

    result = await service.chat(ChatRequest(messages=[user]))
    assert provider.generate_response.await_count == 1
    assert result.messages[-1].content == "Hi!"


@pytest.mark.asyncio
async def test_retry_on_lowercase_style_mismatch() -> None:
    user = ChatMessage(role="user", content="hey there")
    provider = _make_provider()
    provider.generate_response = AsyncMock(side_effect=["Hi there", "hi there"])
    service = AIService(provider)

    result = await service.chat(ChatRequest(messages=[user]))
    assert provider.generate_response.await_count == 2
    assert result.messages[-1].content == "hi there"


@pytest.mark.asyncio
async def test_retry_on_substring_overlap() -> None:
    user = ChatMessage(role="user", content="tell me a joke")
    assistant = ChatMessage(role="assistant", content="knock knock")
    provider = _make_provider()
    provider.generate_response = AsyncMock(side_effect=["knock knock who?", "something else"])
    service = AIService(provider)

    result = await service.chat(ChatRequest(messages=[user, assistant]))
    assert provider.generate_response.await_count == 2
    args = provider.generate_response.await_args_list[1][1]
    assert args["messages"][-1].role == "user"
    assert result.messages[-1].content == "something else"


@pytest.mark.asyncio
async def test_retry_on_user_echo() -> None:
    user = ChatMessage(role="user", content="you broke it")
    provider = _make_provider()
    provider.generate_response = AsyncMock(side_effect=["you broke it again", "fixed now"])
    service = AIService(provider)

    result = await service.chat(ChatRequest(messages=[user]))
    assert provider.generate_response.await_count == 2
    assert result.messages[-1].content == "fixed now"
