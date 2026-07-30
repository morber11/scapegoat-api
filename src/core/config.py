import os
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from providers.base import ProviderName

DEFAULT_REQUEST_TIMEOUT_SECONDS: int = 30
DEFAULT_RATE_LIMIT_REQUESTS: int = 5
DEFAULT_RATE_LIMIT_WINDOW_SECONDS: int = 60


class ConfigNotSetError(Exception):
    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(
            f"{field} is not set. Copy .env.example to .env and fill in the value."
        )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    provider: ProviderName = ProviderName.GEMINI
    request_timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS

    rate_limit_requests: int = DEFAULT_RATE_LIMIT_REQUESTS
    rate_limit_window_seconds: int = DEFAULT_RATE_LIMIT_WINDOW_SECONDS

    max_input_tokens: int = 1024

    provider_api_key: str = ""
    provider_model: str = ""

    allowed_origins: Annotated[list[str], NoDecode] = []

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    env_file = None if os.environ.get("PYTEST_CURRENT_TEST") else ".env"
    # pydantic's BaseSettings accepts `_env_file` at runtime, but the stubbed
    # signature can confuse static checkers. Use a narrow `type: ignore` here
    # to preserve intended runtime behavior (do not load `.env` during tests).
    return Settings(_env_file=env_file)  # type: ignore[call-arg]
