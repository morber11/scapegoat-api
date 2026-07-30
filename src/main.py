import logging
import tomllib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import RateLimitMiddleware
from api.routes import chat, health
from core.config import ConfigNotSetError, get_settings

logging.basicConfig(level=logging.INFO)

try:
    _version = tomllib.loads(
        Path(__file__).parent.parent.joinpath("pyproject.toml").read_text()
    )["project"]["version"]
except Exception:
    _version = "0.0.0"


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()

    if not settings.provider_api_key:
        raise ConfigNotSetError("PROVIDER_API_KEY")
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Scapegoat API",
        description="because we all need someone to blame",
        version=_version,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    origins = settings.allowed_origins
    if not origins:
        if not settings.is_production:
            origins = ["*"]
        else:
            raise RuntimeError(
                "ALLOWED_ORIGINS is empty in production. "
                "Set ALLOWED_ORIGINS in .env"
            )

    logging.info("CORS allowed origins: %s", origins)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_private_network=True,
    )

    app.add_middleware(RateLimitMiddleware)

    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(health.router)

    return app


app = create_app()
