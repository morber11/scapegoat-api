import pytest

from core.config import ConfigNotSetError, get_settings


def test_lifespan_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("PROVIDER_API_KEY", raising=False)
    get_settings.cache_clear()

    from fastapi.testclient import TestClient

    from main import create_app

    with pytest.raises(ConfigNotSetError), TestClient(create_app()):
        pass
