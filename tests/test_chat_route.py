import asyncio

from fastapi.testclient import TestClient

import api.middleware as middleware
from core.config import get_settings


def test_chat_returns_200(client: TestClient) -> None:
    payload = {"messages": [{"role": "user", "content": "Hello!"}]}
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "messages" in body


def test_chat_reply_echoes_message(client: TestClient) -> None:
    payload = {"messages": [{"role": "user", "content": "ping"}]}
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    assert "ping" in response.json()["messages"][-1]["content"]


def test_chat_empty_message_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": ""}]})
    assert response.status_code == 422

    response2 = client.post("/api/v1/chat", json={"message": ""})
    assert response2.status_code == 422


def test_chat_missing_message_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/chat", json={})
    assert response.status_code == 422


def test_chat_invalid_role_is_rejected(client: TestClient) -> None:
    payload = {"messages": [{"role": "assistant", "content": "hi"}]}
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 422


def test_provider_error_returns_502(client: TestClient) -> None:
    from providers.base import ProviderError
    from services.ai_service import AIService

    class BrokenProvider:
        @property
        def provider_name(self) -> str:
            return "broken"

        @property
        def model_name(self) -> str:
            return "none"

        async def generate_response(self, system_prompt: str, messages: list) -> str:
            raise ProviderError("broken", "simulated failure")

    def broken_service() -> AIService:
        return AIService(BrokenProvider())

    from api import get_ai_service
    client.app.dependency_overrides[get_ai_service] = broken_service

    payload = {"messages": [{"role": "user", "content": "hello"}]}
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 502
    assert "simulated failure" in response.text


def test_timeout_returns_504(client: TestClient) -> None:
    class StuckProvider:
        @property
        def provider_name(self) -> str:
            return "stuck"

        @property
        def model_name(self) -> str:
            return "none"

        async def generate_response(self, system_prompt: str, messages: list) -> str:
            await asyncio.sleep(60)
            return "never"

    from services.ai_service import AIService
    def stuck_service() -> AIService:
        return AIService(StuckProvider())

    from api.dependencies import get_ai_service
    client.app.dependency_overrides[get_ai_service] = stuck_service

    settings = get_settings()
    settings.request_timeout_seconds = 0.01

    payload = {"messages": [{"role": "user", "content": "hello"}]}
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 504
    assert f"{settings.request_timeout_seconds}" in response.text
    assert "timed out" in response.text


def test_rate_limit_blocks_excess_requests(client: TestClient) -> None:
    client.raise_server_exceptions = False

    settings = get_settings()
    settings.rate_limit_requests = 2
    settings.rate_limit_window_seconds = 1
    middleware.reset_rate_limits()

    payload = {"messages": [{"role": "user", "content": "hi"}]}
    r1 = client.post("/api/v1/chat", json=payload)
    assert r1.status_code == 200
    r2 = client.post("/api/v1/chat", json=payload)
    assert r2.status_code == 200

    r3 = client.post("/api/v1/chat", json=payload)
    assert r3.status_code == 429
    assert "rate limit" in r3.json().get("detail", "").lower()


def test_rate_limit_resets_after_window(client: TestClient, monkeypatch) -> None:
    client.raise_server_exceptions = False
    settings = get_settings()
    settings.rate_limit_requests = 1
    settings.rate_limit_window_seconds = 10
    middleware.reset_rate_limits()

    fake_time = 1000.0

    def fake_monotonic() -> float:
        return fake_time

    monkeypatch.setattr(middleware.time, "monotonic", fake_monotonic)

    payload = {"messages": [{"role": "user", "content": "ok"}]}
    r1 = client.post("/api/v1/chat", json=payload)
    assert r1.status_code == 200

    r2 = client.post("/api/v1/chat", json=payload)
    assert r2.status_code == 429

    fake_time = 1000.0 + settings.rate_limit_window_seconds + 1

    r3 = client.post("/api/v1/chat", json=payload)
    assert r3.status_code == 200

