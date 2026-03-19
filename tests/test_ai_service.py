from unittest.mock import AsyncMock, MagicMock

import pytest

from core.constants.prompts import SYSTEM_PERSONALITY_PROMPT
from providers.base import ProviderError
from schemas.chat import ChatMessage, ChatRequest
from services.ai_service import AIService
from services.token_utils import estimate_tokens


def _make_provider(reply: str = "hello") -> MagicMock:
    provider = MagicMock()
    provider.provider_name = "mock"
    provider.model_name = "mock-model"
    provider.generate_response = AsyncMock(return_value=reply)
    return provider


@pytest.fixture(autouse=True)
def patch_sleep(monkeypatch):
    sleeper = AsyncMock()
    monkeypatch.setattr("services.ai_service.asyncio.sleep", sleeper)
    return sleeper


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
async def test_provider_error_retries_and_propagates(patch_sleep) -> None:
    provider = _make_provider()
    provider.generate_response = AsyncMock(side_effect=[
        ProviderError("mock", "rate limit exceeded"),
        ProviderError("mock", "rate limit exceeded"),
        ProviderError("mock", "rate limit exceeded"),
    ])
    service = AIService(provider)

    msg = ChatMessage(role="user", content="hello")
    with pytest.raises(ProviderError, match="rate limit exceeded"):
        await service.chat(ChatRequest(messages=[msg]))

    assert provider.generate_response.await_count == 3
    # we should have paused at least once while retrying
    assert patch_sleep.await_count >= 1


@pytest.mark.asyncio
async def test_provider_error_then_success(patch_sleep) -> None:
    provider = _make_provider()
    provider.generate_response = AsyncMock(side_effect=[
        ProviderError("mock", "oops"),
        "okay",
    ])
    service = AIService(provider)

    result = await service.chat(ChatRequest(messages=[ChatMessage(role="user", content="hello")]))
    assert provider.generate_response.await_count == 2
    patch_sleep.assert_awaited_once_with(3)
    assert result.messages[-1].content == "okay"


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
async def test_append_period_when_user_ends_with_dot() -> None:
    user = ChatMessage(role="user", content="please respond.")
    provider = _make_provider("sure")
    service = AIService(provider)

    result = await service.chat(ChatRequest(messages=[user]))

    # should not retry
    assert provider.generate_response.await_count == 1
    assert result.messages[-1].content == "sure."


@pytest.mark.asyncio
async def test_no_append_if_reply_already_has_dot() -> None:
    user = ChatMessage(role="user", content="hello world.")
    provider = _make_provider("already.")
    service = AIService(provider)

    result = await service.chat(ChatRequest(messages=[user]))
    assert provider.generate_response.await_count == 1
    assert result.messages[-1].content == "already."


@pytest.mark.asyncio
async def test_reprompt_not_seen_as_user_message() -> None:
    user = ChatMessage(role="user", content="Hello there.")
    provider = _make_provider()
    provider.generate_response = AsyncMock(side_effect=["hi", "Hi there."])
    service = AIService(provider)

    await service.chat(ChatRequest(messages=[user]))

    second_msgs = provider.generate_response.await_args_list[1][1]["messages"]
    assert all("capitalise" not in m.content.lower() for m in second_msgs)


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
async def test_no_trimming_when_under_budget() -> None:
    provider = _make_provider("ok")
    provider.generate_response = AsyncMock(return_value="ok")
    service = AIService(provider)

    from core.config import get_settings

    settings = get_settings()
    settings.max_input_tokens = 10000

    user = ChatMessage(role="user", content="short")
    await service.chat(ChatRequest(messages=[user]))
    sent = provider.generate_response.await_args_list[0][1]["messages"]
    assert sent == [user]


@pytest.mark.asyncio
async def test_trimming_happens_when_over_budget() -> None:
    provider = _make_provider("response")
    provider.generate_response = AsyncMock(return_value="response")
    service = AIService(provider)

    from core.config import get_settings
    settings = get_settings()
    msgs = [ChatMessage(role="user", content="x" * 10) for _ in range(5)]
    full = estimate_tokens(SYSTEM_PERSONALITY_PROMPT, msgs)
    settings.max_input_tokens = full - 1

    await service.chat(ChatRequest(messages=list(msgs)))

    sent = provider.generate_response.await_args_list[0][1]["messages"]
    assert len(sent) < len(msgs)
    assert sent == msgs[-len(sent):] if sent else sent == []


@pytest.mark.asyncio
async def test_trimming_applies_on_retry() -> None:
    provider = _make_provider()
    provider.generate_response = AsyncMock(side_effect=["World", "again"])
    service = AIService(provider)

    from core.config import get_settings
    settings = get_settings()
    user1 = ChatMessage(role="user", content="hello")
    user2 = ChatMessage(role="user", content="world")
    # choose a budget that keeps one message but not after reprompt
    one_msg_tokens = estimate_tokens(SYSTEM_PERSONALITY_PROMPT, [user1])
    settings.max_input_tokens = one_msg_tokens + 1

    await service.chat(ChatRequest(messages=[user1, user2]))

    assert provider.generate_response.await_count >= 2
    second_args = provider.generate_response.await_args_list[1][1]
    assert len(second_args["messages"]) < 3


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


@pytest.mark.asyncio
async def test_retry_waits_between_attempts(patch_sleep) -> None:
    user = ChatMessage(role="user", content="hello")
    provider = _make_provider()

    provider.generate_response = AsyncMock(side_effect=["", "", "ok"])
    service = AIService(provider)

    await service.chat(ChatRequest(messages=[user]))

    assert patch_sleep.await_count >= 1

@pytest.mark.asyncio
async def test_no_sleep_when_no_retry(patch_sleep) -> None:
    user = ChatMessage(role="user", content="ok")
    provider = _make_provider("ok")
    service = AIService(provider)

    await service.chat(ChatRequest(messages=[user]))
    patch_sleep.assert_not_awaited()
