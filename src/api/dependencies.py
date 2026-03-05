from fastapi import Depends

from core.config import Settings, get_settings
from providers.base import AIProvider
from providers.gemini_provider import GeminiProvider
from services.ai_service import AIService

_settings_dep: Depends = Depends(get_settings)

_provider_cache: AIProvider | None = None


def _build_provider(settings: Settings) -> AIProvider:
    global _provider_cache
    if _provider_cache is None:
        provider_name = settings.provider.lower()

        if provider_name == "gemini":
            _provider_cache = GeminiProvider(settings)
        else:
            raise ValueError(
                f"unknown provider '{settings.provider}'. "
                "check your PROVIDER env var or register the adapter in "
                "src/scapegoat_api/api/dependencies.py."
            )
    return _provider_cache


def get_ai_service(settings: Settings = _settings_dep) -> AIService:
    provider = _build_provider(settings)
    return AIService(provider)
