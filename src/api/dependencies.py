from fastapi import Depends

from core.config import Settings, get_settings
from providers.base import AIProvider, ProviderName
from providers.deepseek_provider import DeepSeekProvider
from providers.gemini_provider import GeminiProvider
from services.ai_service import AIService

_settings_dep = Depends(get_settings)

_provider_cache: AIProvider | None = None


def _build_provider(settings: Settings) -> AIProvider:
    global _provider_cache
    if _provider_cache is None:
        match settings.provider:
            case ProviderName.GEMINI:
                _provider_cache = GeminiProvider(settings)
            case ProviderName.DEEPSEEK:
                _provider_cache = DeepSeekProvider(settings)
            case _:
                raise ValueError(
                    f"unknown provider '{settings.provider}'. "
                    "check your PROVIDER env var or register the adapter in "
                    "src/api/dependencies.py"
                )
    return _provider_cache


def get_ai_service(settings: Settings = _settings_dep) -> AIService:
    provider = _build_provider(settings)
    return AIService(provider)
