import pytest

from core.config import get_settings


def test_lifespan_requires_api_key(monkeypatch) -> None:
    """app startup should fail if the API key is missing."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()

    from fastapi.testclient import TestClient

    from main import create_app

    with pytest.raises(RuntimeError) as excinfo, TestClient(create_app()):
        pass
    assert "gemini_api_key is not set" in str(excinfo.value).lower()
