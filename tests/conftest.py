import osfrom collections.abc import Generatorfrom typing import Anyimport pytestfrom fastapi.testclient import TestClientos.environ.setdefault("PROVIDER_API_KEY", "test-key")

from api.dependencies import get_ai_service
from api.middleware import reset_rate_limits
from core.config import get_settings
from main import app
from schemas.chat import ChatMessage
from services.ai_service import AIService


class StubProvider:

    @property
    def provider_name(self) -> str:
        return "stub"

    @property
    def model_name(self) -> str:
        return "stub-model"

    async def generate_response(self, system_prompt: str, messages: list[ChatMessage]) -> str:
        last = messages[-1].content if messages else ""
        return f"stub reply to: {last}"


def stub_ai_service() -> AIService:
    return AIService(StubProvider())


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    reset_rate_limits()
    yield
    get_settings.cache_clear()
    reset_rate_limits()


@pytest.fixture
def client() -> Generator[TestClient, Any, None]:
    app.dependency_overrides[get_ai_service] = stub_ai_service
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()
